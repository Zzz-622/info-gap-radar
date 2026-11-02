#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深读摘要: 抓取精选 topN 的原文(经免费 r.jina.ai), LLM 写摘要, 追加到精选文件。
需要 DEEPSEEK_API_KEY; 无 key 或单篇抓取失败时优雅跳过。仅标准库。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

RADAR_ROOT = Path(__file__).resolve().parents[1]
PROFILE = RADAR_ROOT / "config" / "profile.json"
PICKS_JSON = RADAR_ROOT / "data" / "latest_picks.json"
REPORTS = RADAR_ROOT / "reports"
API = "https://api.deepseek.com/chat/completions"
JINA = "https://r.jina.ai/"
MODEL = os.environ.get("RADAR_LLM_MODEL", "deepseek-chat")

SYSTEM = """你是深度阅读助手。基于原文内容写中文摘要, 严格三段:
### 摘要
3-5句讲清这篇在说什么(抓主线, 不要罗列细节)
### 为什么重要
结合用户画像(职业与工作/学习成长/投资理财)说1-2句
### 值得记住
1个关键数据、机制或反常识点; 没有就写"无特别值得记的"
原文太碎或抓不到正文就明说, 禁止编造。直接输出 markdown。"""


def fetch_text(url, timeout=45):
    req = urllib.request.Request(JINA + url, headers={
        "User-Agent": "Mozilla/5.0", "X-Return-Format": "markdown"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def summarize(key, text, title):
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"标题: {title}\n\n原文(截断):\n{text[:6000]}"},
        ],
        "max_tokens": 900,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return (resp["choices"][0]["message"]["content"] or "").strip()


def main():
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("未配置 DEEPSEEK_API_KEY, 跳过深读")
        return
    if not PICKS_JSON.exists():
        print("缺少 latest_picks.json, 请先运行 pick_news.py")
        return
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    top_n = int(profile.get("deep_read_top", 3))
    picks = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    items = (picks.get("picks") or [])[:top_n]
    if not items:
        print("今日无精选, 跳过深读")
        return

    sections = []
    for i, p in enumerate(items, 1):
        url = p.get("link", "")
        if not url:
            sections.append(f"### {i}. {p.get('title','')}\n\n（无链接, 跳过深读）")
            continue
        try:
            text = fetch_text(url)
            if len(text.strip()) < 200:
                sections.append(f"### {i}. {p.get('title','')}\n\n（原文抓取内容过少, 深读失败, 请点链接阅读）")
                continue
            summary = summarize(key, text, p.get("title", ""))
            sections.append(f"### {i}. {p.get('title','')}\n\n{summary}")
            print(f"[ok] 深读 {i}: {p.get('title','')[:40]}")
        except Exception as e:
            sections.append(f"### {i}. {p.get('title','')}\n\n（深读失败: {type(e).__name__}, 请点链接阅读）")
            print(f"[fail] 深读 {i}: {e}")

    today = datetime.now().strftime("%Y-%m-%d")
    out = REPORTS / f"radar-{today}-picks.md"
    if not out.exists():
        print("未找到今日精选文件")
        return
    text = out.read_text(encoding="utf-8")
    if "## 📖 深读摘要" not in text:
        text = text.rstrip() + "\n\n## 📖 深读摘要\n\n" + "\n\n---\n\n".join(sections) + "\n"
        out.write_text(text, encoding="utf-8")
        print(f"深读摘要已追加到 {out.name}")
    else:
        print("已有深读章节, 跳过")


if __name__ == "__main__":
    main()
