#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""间隔重复复习调度(0 成本逻辑): 管理 radar/learn/reviews/schedule.json。
用法:
  quiz_radar.py --scan            把 cards/ 里未登记的学习卡加入计划
  quiz_radar.py                   列出今日到期/逾期的复习卡
  quiz_radar.py --done <卡片文件名stem>   标记复习完成, 按 1/3/7/14/30/60 天推进
仅标准库。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

LEARN = Path(__file__).resolve().parents[1] / "learn"
SCHED = LEARN / "reviews" / "schedule.json"
CARDS = LEARN / "cards"
INTERVALS = [1, 3, 7, 14, 30, 60]


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def load():
    if SCHED.exists():
        return json.loads(SCHED.read_text(encoding="utf-8"))
    return {"cards": {}, "log": []}


def save(s):
    SCHED.parent.mkdir(parents=True, exist_ok=True)
    SCHED.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="登记 cards/ 中未入计划的学习卡")
    ap.add_argument("--done", help="标记某张卡复习完成(传文件名, 如 2026-11-01-xxx)")
    args = ap.parse_args()

    sched = load()
    today = today_str()

    if args.scan:
        added = 0
        for f in sorted(CARDS.glob("*.md")):
            stem = f.stem
            if stem not in sched["cards"]:
                sched["cards"][stem] = {"stage": 0, "next_review": today}
                added += 1
        if added:
            save(sched)
        print(f"新登记 {added} 张学习卡, 现有 {len(sched['cards'])} 张")
        return

    if args.done:
        key = args.done
        if key.endswith(".md"):
            key = key[:-3]
        c = sched["cards"].get(key)
        if not c:
            print(f"计划中没有这张卡: {key} (先 --scan)")
            sys.exit(1)
        stage = int(c.get("stage", 0))
        c["stage"] = stage + 1
        days = INTERVALS[min(stage, len(INTERVALS) - 1)]
        nxt = (datetime.now() + __import__("datetime").timedelta(days=days)).strftime("%Y-%m-%d")
        c["next_review"] = nxt
        sched["log"].append({"card": key, "reviewed": today, "stage": c["stage"], "next": nxt})
        save(sched)
        print(f"完成复习: {key} -> 第 {c['stage']} 轮, 下次 {nxt}")
        return

    # 默认: 列出到期卡片
    due = []
    for key, c in sched["cards"].items():
        if c.get("next_review", "") <= today:
            due.append((key, c.get("stage", 0), c.get("next_review", "?")))
    if not due:
        print("今日没有到期复习。")
    else:
        print(f"今日到期 {len(due)} 张:")
        for key, stage, nxt in sorted(due):
            print(f"  [第{stage + 1}轮] {key}  (原定 {nxt})")


if __name__ == "__main__":
    main()
