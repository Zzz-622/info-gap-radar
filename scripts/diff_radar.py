#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息差雷达差异分析+告警: 对比快照 -> 新增/变化/告警 -> radar/data/latest_diff.json。仅标准库。"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RADAR_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = RADAR_ROOT / "data" / "radar.db"
CFG_ALERTS = RADAR_ROOT / "config" / "alerts.json"
OUT = RADAR_ROOT / "data" / "latest_diff.json"


def main():
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    db = sqlite3.connect(DB_PATH)
    rows = db.execute("SELECT DISTINCT last_run_ts FROM items ORDER BY last_run_ts DESC LIMIT 2").fetchall()
    if not rows:
        print("快照为空: 请先运行 fetch_radar.py")
        sys.exit(1)
    latest = rows[0][0]

    alerts_cfg = json.loads(CFG_ALERTS.read_text(encoding="utf-8"))
    keywords = [str(k).lower() for k in alerts_cfg.get("keywords", [])]
    min_hot = float(alerts_cfg.get("min_hot") or 0)
    priority = set(alerts_cfg.get("priority_domains") or [])
    caps = alerts_cfg.get("caps") or {}

    def fetch_items(extra_where, params, limit=None):
        q = ("SELECT id,source_name,domain,title,link,extra FROM items "
             "WHERE last_run_ts=? " + extra_where)
        args = [latest] + params
        if limit:
            q += " LIMIT ?"
            args.append(limit)
        out = []
        for id_, sn, dom, title, link, extra in db.execute(q, args):
            out.append({"id": id_, "source": sn, "domain": dom, "title": title,
                        "link": link, "extra": json.loads(extra or "{}")})
        return out

    new_all = fetch_items("AND first_run_ts=?", [latest])
    updated = fetch_items("AND first_run_ts<? AND run_count>1", [latest],
                          caps.get("updated", 60))

    # 按领域均衡取样, 保证每个领域都出现在日报里(避免大领域挤掉小领域)
    by_dom = {}
    for it in new_all:
        by_dom.setdefault(it["domain"] or "未分类", []).append(it)
    new_items = []
    per_dom = int(caps.get("new_per_domain", 15))
    for its in by_dom.values():
        new_items.extend(its[:per_dom])
    new_items = new_items[: int(caps.get("new", 400))]

    top_hot = []
    for id_, sn, dom, title, link, extra in db.execute(
            "SELECT id,source_name,domain,title,link,extra FROM items WHERE last_run_ts=? "
            "ORDER BY CAST(json_extract(extra,'$.hot_num') AS REAL) DESC LIMIT ?",
            (latest, caps.get("top_hot", 15))):
        top_hot.append({"id": id_, "source": sn, "domain": dom, "title": title, "link": link,
                        "hot": (json.loads(extra or "{}") or {}).get("hot")})

    alerts = []
    for it in new_all:
        low = (it["title"] or "").lower()
        hit_kw = [k for k in keywords if k and k in low]
        hot_num = float((it["extra"] or {}).get("hot_num") or 0)
        is_priority = (it["domain"] or "") in priority
        if hit_kw or (min_hot > 0 and hot_num >= min_hot) or is_priority:
            alerts.append({**it, "why": {"keywords": hit_kw, "hot": bool(min_hot > 0 and hot_num >= min_hot),
                                         "priority_domain": is_priority}})

    diff = {"ts": latest, "time": datetime.now().isoformat(timespec="seconds"),
            "counts": {"new": len(new_all), "updated": len(updated), "alerts": len(alerts)},
            "new": new_items, "updated": updated,
            "alerts": alerts[: caps.get("alerts", 40)], "top_hot": top_hot}
    OUT.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"新增 {len(new_all)} / 变化 {len(updated)} / 告警 {len(alerts)} / 热度TOP {len(top_hot)}")
    for a in alerts[:10]:
        print(f"  [ALERT] [{a['domain']}] {a['title']}")
    db.close()


if __name__ == "__main__":
    main()
