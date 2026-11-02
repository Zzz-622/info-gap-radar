#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息差雷达采集器: 免费公开源 -> 归一化 -> SQLite 快照。仅用标准库, 无 pip 依赖。"""
import argparse
import hashlib
import json
import re
import sqlite3
import ssl
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

RADAR_ROOT = Path(__file__).resolve().parents[1]
CFG_SRC = RADAR_ROOT / "config" / "sources.json"
CFG_ALERTS = RADAR_ROOT / "config" / "alerts.json"
DB_PATH = RADAR_ROOT / "data" / "radar.db"
LAST_RUN = RADAR_ROOT / "data" / "last_run.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 DSH-InfoRadar/0.1")


def log(msg):
    print(msg, flush=True)


def http_get(url, timeout=20):
    """请求公开只读数据; 证书链不完整时降级重试一次(仅对无认证公开源)。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=ssl._create_unverified_context()) as r:
                return r.read()
        raise


def norm_item(source, title, link="", extra=None, item_id=None):
    title = (title or "").strip()
    if not title:
        return None
    if item_id is None:
        item_id = hashlib.sha1(f"{source['id']}|{title[:120]}".encode("utf-8")).hexdigest()[:24]
    return {"id": item_id, "title": title, "link": link or "", "extra": extra or {}}


def to_hot_num(hot):
    """'1234567' / '123.4万' / '1.2亿' -> float"""
    try:
        s = str(hot).replace(",", "").strip()
        if not s:
            return 0.0
        s = s.replace("万", "e4").replace("亿", "e8")
        return float(s)
    except Exception:
        return 0.0


# ---------------- 各类型解析器 ----------------
def parse_rss(source, data):
    """兼容 RSS 2.0 与 Atom。"""
    out = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        log(f"  [warn] {source['id']}: RSS 解析失败 {e}")
        return out
    atom_ns = "{http://www.w3.org/2005/Atom}"
    if root.tag == atom_ns + "feed":
        # Atom feed (如 The Verge)
        for e in root.findall(atom_ns + "entry"):
            def at(tag):
                el = e.find(atom_ns + tag)
                return (el.text or "").strip() if el is not None and el.text else ""
            lk = e.find(atom_ns + "link")
            link = (lk.get("href") or "").strip() if lk is not None else ""
            out.append(norm_item(source, at("title"), link,
                                 {"desc": re.sub(r"<[^>]+>", "", at("summary"))[:200],
                                  "pub": at("updated")}))
        return out
    # RSS 2.0
    for it in root.iter("item"):
        def t(tag):
            el = it.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        title = t("title")
        link = t("link")
        desc = re.sub(r"<[^>]+>", "", t("description"))[:200]
        out.append(norm_item(source, title, link, {"desc": desc, "pub": t("pubDate")}))
    return out


def parse_hotlist(source, data):
    out = []
    try:
        obj = json.loads(data.decode("utf-8", "replace"))
        for d in (obj.get("data") or []):
            hot = d.get("hot", "")
            out.append(norm_item(source, d.get("title"), d.get("url") or d.get("mobilUrl") or "",
                                 {"rank": d.get("index"), "hot": hot, "hot_num": to_hot_num(hot)}))
    except Exception as e:
        log(f"  [warn] {source['id']}: 解析失败 {e}")
    return out


def parse_hn(source, data):
    out = []
    try:
        obj = json.loads(data.decode("utf-8", "replace"))
        for h in (obj.get("hits") or [])[:30]:
            link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            out.append(norm_item(source, h.get("title"), link,
                                 {"points": h.get("points"), "comments": h.get("num_comments")},
                                 item_id=f"hn-{h.get('objectID')}"))
    except Exception as e:
        log(f"  [warn] {source['id']}: 解析失败 {e}")
    return out


def parse_github_trending(source, data):
    out = []
    try:
        html = data.decode("utf-8", "replace")
        seen = set()
        for m in re.finditer(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"[^>]*>', html):
            repo = m.group(1).strip()
            if repo.count("/") == 1 and repo not in seen and not repo.startswith(("trending/", "sponsors/", "collections")):
                seen.add(repo)
                out.append(norm_item(source, repo, "https://github.com/" + repo, {}))
        out = out[:25]
    except Exception as e:
        log(f"  [warn] {source['id']}: 解析失败 {e}")
    return out


def parse_arxiv(source, data):
    out = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(data)
        for e in root.findall("a:entry", ns):
            title = " ".join((e.findtext("a:title", "", ns) or "").split())
            link = e.findtext("a:id", "", ns) or ""
            pub = e.findtext("a:published", "", ns) or ""
            summ = " ".join((e.findtext("a:summary", "", ns) or "").split())[:200]
            out.append(norm_item(source, title, link, {"pub": pub, "abs": summ}, item_id=link))
    except ET.ParseError as e:
        log(f"  [warn] {source['id']}: 解析失败 {e}")
    return out


def parse_fx(source, data):
    out = []
    try:
        obj = json.loads(data.decode("utf-8", "replace"))
        cny = (obj.get("rates") or {}).get("CNY")
        if cny:
            out.append(norm_item(source, "USD/CNY = %.4f" % cny, source["url"],
                                 {"rate": cny}, item_id="fx-usd-cny"))
    except Exception as e:
        log(f"  [warn] {source['id']}: 解析失败 {e}")
    return out


def parse_tophub(source, data):
    """tophub.today 榜单页: <tr> 行内 target=_blank 的标题链接 + 行尾热度数字。"""
    out = []
    try:
        html = data.decode("utf-8", "replace")
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            m = re.search(r'href="([^"]+)"[^>]*target="_blank"[^>]*>(.*?)</a>', row, re.S)
            if not m:
                continue
            link, inner = m.group(1), m.group(2)
            if "tophubdata.com" in link or "tophub.today" in link:
                continue
            if not link.startswith("http"):
                continue  # 页面内嵌 JS 模板字符串, 不是真实条目
            title = re.sub(r"<[^>]+>", "", inner).strip()
            if not title or len(title) > 120 or "'" in title or " + " in title:
                continue
            hot = ""
            for tdv in re.findall(r"<td[^>]*>([\d,.万]+)</td>", row):
                hot = tdv
            out.append(norm_item(source, title, link, {"hot": hot, "hot_num": to_hot_num(hot)}))
    except Exception as e:
        log(f"  [warn] {source['id']}: 解析失败 {e}")
    return out


def parse_bili_popular(source, data):
    out = []
    try:
        obj = json.loads(data.decode("utf-8", "replace"))
        for v in (obj.get("data") or {}).get("list") or []:
            title = v.get("title")
            aid = v.get("aid")
            stat = v.get("stat") or {}
            owner = (v.get("owner") or {}).get("name", "")
            out.append(norm_item(source, title, f"https://www.bilibili.com/video/av{aid}",
                                 {"view": stat.get("view"), "owner": owner},
                                 item_id=f"bili-av{aid}"))
    except Exception as e:
        log(f"  [warn] {source['id']}: 解析失败 {e}")
    return out


PARSERS = {
    "rss": parse_rss,
    "hotlist": parse_hotlist,
    "hn": parse_hn,
    "github_trending": parse_github_trending,
    "arxiv": parse_arxiv,
    "fx": parse_fx,
    "tophub": parse_tophub,
    "bili_popular": parse_bili_popular,
}


def init_db(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS items(
      id TEXT PRIMARY KEY, source_id TEXT, source_name TEXT, domain TEXT,
      title TEXT, link TEXT, extra TEXT,
      first_run_ts INTEGER, last_run_ts INTEGER, run_count INTEGER DEFAULT 1);
    CREATE INDEX IF NOT EXISTS idx_items_run ON items(last_run_ts);
    CREATE TABLE IF NOT EXISTS runs(ts INTEGER PRIMARY KEY, sources INTEGER, items INTEGER, errors TEXT);
    """)


def main():
    ap = argparse.ArgumentParser(description="信息差雷达采集器")
    ap.add_argument("--once", help="只采集指定 source id(调试)")
    ap.add_argument("--limit", type=int, default=30, help="每源最多保留条数")
    ap.add_argument("--keep-days", type=int, default=45, help="快照保留天数, 过期条目清理")
    args = ap.parse_args()

    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sources = json.loads(CFG_SRC.read_text(encoding="utf-8")).get("sources", [])
    try:
        alerts_cfg = json.loads(CFG_ALERTS.read_text(encoding="utf-8"))
    except Exception:
        alerts_cfg = {}
    exclude_kws = [str(k).lower() for k in alerts_cfg.get("exclude_keywords", [])]
    if args.once:
        sources = [s for s in sources if s.get("id") == args.once]
        if not sources:
            log(f"未找到源: {args.once}")
            sys.exit(2)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    init_db(db)
    run_ts = int(time.time())
    per_source, errors = [], []
    for s in sources:
        src_id, stype = s.get("id"), s.get("type")
        parser = PARSERS.get(stype)
        if stype == "hotlist":
            url = "https://api.vvhan.com/api/hotlist?type=" + (s.get("kind") or "")
        else:
            url = s.get("url")
        if not parser or not url:
            log(f"[skip] {src_id}: 未知类型或缺少 url/kind")
            errors.append(f"{src_id}: bad-config")
            continue
        try:
            data = http_get(url)
            items = (parser(s, data) or [])[: args.limit]
            before = len(items)
            items = [it for it in items
                     if not any(k and k in it["title"].lower() for k in exclude_kws)]
            if len(items) < before:
                log(f"    过滤娱乐/八卦类 {before - len(items)} 条")
            new = 0
            for it in items:
                cur = db.execute("SELECT run_count FROM items WHERE id=?", (it["id"],)).fetchone()
                if cur is None:
                    new += 1
                    db.execute(
                        "INSERT INTO items(id,source_id,source_name,domain,title,link,extra,first_run_ts,last_run_ts,run_count)"
                        " VALUES(?,?,?,?,?,?,?,?,?,1)",
                        (it["id"], src_id, s.get("name", ""), s.get("domain", ""),
                         it["title"], it["link"], json.dumps(it["extra"], ensure_ascii=False), run_ts, run_ts))
                else:
                    db.execute(
                        "UPDATE items SET title=?,link=?,extra=?,last_run_ts=?,run_count=? WHERE id=?",
                        (it["title"], it["link"], json.dumps(it["extra"], ensure_ascii=False),
                         run_ts, cur[0] + 1, it["id"]))
            per_source.append({"id": src_id, "fetched": len(items), "new": new})
            log(f"[ok] {src_id}: {len(items)} 条, 新增 {new}")
        except Exception as e:
            msg = f"{src_id}: {type(e).__name__}: {e}"
            log(f"[fail] {msg}")
            errors.append(msg)
        db.commit()

    cutoff = run_ts - args.keep_days * 86400
    db.execute("DELETE FROM items WHERE last_run_ts < ?", (cutoff,))
    db.execute("INSERT INTO runs(ts,sources,items,errors) VALUES(?,?,?,?)",
               (run_ts, len(per_source), sum(p["fetched"] for p in per_source),
                json.dumps(errors, ensure_ascii=False)))
    db.commit()
    total_items = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    summary = {"run_ts": run_ts, "time": datetime.now().isoformat(timespec="seconds"),
               "per_source": per_source, "errors": errors, "db_items": total_items}
    LAST_RUN.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"完成: {len(per_source)} 源成功 / {len(errors)} 源失败 / 库中条目 {total_items}")
    db.close()


if __name__ == "__main__":
    main()
