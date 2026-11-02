#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""0 成本日报生成器(不需要 LLM): 读取 latest_diff.json -> Markdown 日报。仅标准库。"""
import json
import sys
from datetime import datetime
from pathlib import Path

RADAR_ROOT = Path(__file__).resolve().parents[1]
DIFF = RADAR_ROOT / "data" / "latest_diff.json"
REPORTS = RADAR_ROOT / "reports"


def esc(t):
    return (t or "").replace("|", "\\|")


def main():
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not DIFF.exists():
        print("无差异数据: 请先运行 fetch_radar.py 与 diff_radar.py")
        sys.exit(1)
    d = json.loads(DIFF.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")
    REPORTS.mkdir(parents=True, exist_ok=True)
    L = []
    A = L.append
    A("# 信息差雷达日报 · " + today)
    A("")
    A(f"> 数据时间: {d['time']} · 新增 {d['counts']['new']} / 变化 {d['counts']['updated']} / 告警 {d['counts']['alerts']} · 自动生成(0 成本模式)")
    A("")
    A("## 🚨 告警信号")
    A("")
    if d["alerts"]:
        for a in d["alerts"]:
            parts = []
            if a["why"]["keywords"]:
                parts.append("命中关键词 " + "/".join(a["why"]["keywords"]))
            if a["why"]["hot"]:
                parts.append("热度超阈值")
            if a["why"]["priority_domain"]:
                parts.append("优先领域")
            why = "；".join(parts)
            A(f"- [{a['domain']}] [{esc(a['title'])}]({a.get('link') or '#'}) — {why}")
    else:
        A("（今日无命中规则的信号）")
    A("")
    A(f"## 🔥 热度 TOP{len(d['top_hot'])}")
    A("")
    for h in d["top_hot"]:
        A(f"- [{h['domain']}] [{esc(h['title'])}]({h.get('link') or '#'}) · 热度 {h.get('hot') or '-'}")
    A("")
    A("## 🆕 今日新增（按领域）")
    by_domain = {}
    for it in d["new"]:
        by_domain.setdefault(it["domain"] or "未分类", []).append(it)
    for dom, items in by_domain.items():
        A("")
        A(f"### {dom}（{len(items)}）")
        for it in items[:12]:
            A(f"- [{esc(it['title'])}]({it.get('link') or '#'}) · {it['source']}")
    A("")
    A("## 📌 变化条目")
    A("")
    for it in d["updated"][:10]:
        A(f"- [{it['domain']}] {esc(it['title'])}")
    A("")
    A("---")
    A("*本报告由雷达脚本自动生成；如需 LLM 深度解读，在 DSH 中说「用 radar-report skill 解读今日雷达」。*")
    out = REPORTS / f"radar-{today}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"已生成 {out}")


if __name__ == "__main__":
    main()
