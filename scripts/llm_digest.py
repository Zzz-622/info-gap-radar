#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 雷达解读: 读 latest_diff.json, 调 DeepSeek API, 把解读追加到当日日报。
未设 DEEPSEEK_API_KEY 环境变量时静默跳过(退出码 0), 0 成本模式不受影响。仅标准库。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

RADAR_ROOT = Path(__file__).resolve().parents[1]
DIFF = RADAR_ROOT / "data" / "latest_diff.json"
REPORTS = RADAR_ROOT / "reports"
API = "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("RADAR_LLM_MODEL", "deepseek-chat")

SYSTEM = (
    "你是信息差雷达的分析员。基于给定的今日信号(告警/热度榜/各领域新增), 写一段中文『雷达解读』: "
    "1) 有什么大多数人还没注意到但值得注意的变化; 2) 什么信号与主流叙事相反; 3) 未来7天可能发酵什么。"
    "每条给可行动作或'仅观察'判断。全文不超过600字, 用 markdown 小标题组织, 标注来源名称, 禁止编造, "
    "数据不足就明说。直接输出解读正文, 不要客套。"
)


def main():
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("未配置 DEEPSEEK_API_KEY, 跳过 LLM 解读(0 成本模式)")
        return
    if not DIFF.exists():
        print("缺少 latest_diff.json, 请先运行 fetch/diff")
        sys.exit(1)
    d = json.loads(DIFF.read_text(encoding="utf-8"))
    payload = {
        "counts": d.get("counts", {}),
        "alerts": d.get("alerts", [])[:40],
        "top_hot": d.get("top_hot", [])[:15],
        "new_by_domain": {},
    }
    for it in d.get("new", []):
        payload["new_by_domain"].setdefault(it["domain"], []).append(
            {"t": it["title"], "s": it["source"]})
    for k in payload["new_by_domain"]:
        payload["new_by_domain"][k] = payload["new_by_domain"][k][:10]

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "max_tokens": 1200,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode("utf-8"))
    digest = (resp["choices"][0]["message"]["content"] or "").strip()
    if not digest:
        print("LLM 返回为空")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    report = REPORTS / f"radar-{today}.md"
    if not report.exists():
        cand = sorted(REPORTS.glob("radar-*.md"))
        if not cand:
            print("未找到日报文件, 解读跳过")
            return
        report = cand[-1]
    text = report.read_text(encoding="utf-8")
    if "## 🧭 雷达解读" not in text:
        text = text.rstrip() + "\n\n## 🧭 雷达解读（LLM）\n\n" + digest + "\n"
        report.write_text(text, encoding="utf-8")
        print(f"已追加解读到 {report.name} ({len(digest)} 字)")
    else:
        print("日报已有解读章节, 跳过")


if __name__ == "__main__":
    main()
