#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个性化精选(私人编辑): 按用户画像从今日信号中筛出最有用新闻。
有 DEEPSEEK_API_KEY 走 LLM 判断; 无 key 退化为 0 成本规则精选。仅标准库。
输出: radar/data/latest_picks.json + radar/reports/radar-YYYY-MM-DD-picks.md
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

RADAR_ROOT = Path(__file__).resolve().parents[1]
DIFF = RADAR_ROOT / "data" / "latest_diff.json"
PROFILE = RADAR_ROOT / "config" / "profile.json"
REPORTS = RADAR_ROOT / "reports"
PICKS_JSON = RADAR_ROOT / "data" / "latest_picks.json"
API = "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("RADAR_LLM_MODEL", "deepseek-chat")

SYSTEM = """你是用户的私人新闻编辑。任务: 从今日信号中筛出对用户"真正有用"的新闻(不是单纯的热闹)。
用户画像: {profile}
筛选标准(按重要性): 1)与用户用途强相关 2)信息差强度(少有人注意但值得注意) 3)可行动性(看完能做什么) 4)长期价值(值得进学习主题) 5)多源交叉出现=强信号。
排除: 纯流量话题、标题党、与画像无关的日常琐事、同主题重复(只留信息量最大的一条)。
输出严格 JSON(不要 markdown 代码块, 不要任何解释文字):
{{"picks":[{{"title":"...","link":"...","source":"...","domain":"...","score":0,"reason":"为什么对用户有用(一句话)","action":"可行动作或'仅观察'"}}],"noise_note":"一句话说明今天排除了哪些类型的内容"}}
picks 最多 {max_picks} 条, 按 score 降序; 没有值得选的就输出空数组并在 noise_note 说明。"""


def build_payload(d):
    payload = {
        "counts": d.get("counts", {}),
        "alerts": d.get("alerts", [])[:60],
        "top_hot": d.get("top_hot", [])[:15],
        "new_by_domain": {},
    }
    for it in d.get("new", []):
        payload["new_by_domain"].setdefault(it["domain"], []).append(
            {"t": it["title"], "l": it.get("link", ""), "s": it["source"]})
    for k in payload["new_by_domain"]:
        payload["new_by_domain"][k] = payload["new_by_domain"][k][:10]
    return payload


def rule_pick(d, profile):
    """0 成本规则精选: 兴趣词/加权领域命中 + 告警热度加权。"""
    interests = [str(k).lower() for k in profile.get("interests", [])]
    boost = set(profile.get("boost_domains", []))
    exclude = [str(k).lower() for k in profile.get("exclude", [])]
    max_picks = int(profile.get("max_picks", 10))
    pool = {}

    def add(it, w):
        if it.get("id") in pool:
            pool[it["id"]]["w"] = max(pool[it["id"]]["w"], w)
            return
        pool[it.get("id")] = {**it, "w": w}

    for a in d.get("alerts", []):
        add(a, 3)
    for h in d.get("top_hot", [])[:20]:
        add(h, 1)
    for it in d.get("new", []):
        low = (it.get("title") or "").lower()
        w = sum(1 for k in interests if k and k in low)
        if (it.get("domain") or "") in boost:
            w += 1
        if w > 0:
            add(it, w + 1)

    cand = [v for v in pool.values()
            if not any(k and k in (v.get("title") or "").lower() for k in exclude)]
    cand.sort(key=lambda v: (-v["w"], -float((v.get("extra") or {}).get("hot_num") or 0)))
    picks, seen = [], set()
    for v in cand:
        if len(picks) >= max_picks:
            break
        if v.get("title") in seen:
            continue
        seen.add(v["title"])
        kw = [k for k in interests if k and k in (v.get("title") or "").lower()][:3]
        picks.append({"title": v["title"], "link": v.get("link", ""), "source": v["source"],
                      "domain": v["domain"], "score": v["w"] * 10,
                      "reason": ("命中兴趣词: " + "/".join(kw)) if kw else "告警或优先领域信号",
                      "action": "仅观察"})
    return picks, "规则模式(未配置 LLM): 按画像关键词与加权领域筛选, 结果较粗"


def llm_pick(payload, profile, key, max_picks):
    system = SYSTEM.format(profile=json.dumps(profile, ensure_ascii=False),
                           max_picks=max_picks)
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "max_tokens": 1800,
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode("utf-8"))
    raw = (resp["choices"][0]["message"]["content"] or "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    obj = json.loads(m.group(0) if m else raw)
    picks = obj.get("picks") or []
    noise = obj.get("noise_note") or ""
    return picks, noise


def main():
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not DIFF.exists():
        print("缺少 latest_diff.json, 请先运行 fetch/diff")
        sys.exit(1)
    d = json.loads(DIFF.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    max_picks = int(profile.get("max_picks", 10))
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()

    if key:
        try:
            picks, noise = llm_pick(build_payload(d), profile, key, max_picks)
            mode = "LLM 精选"
        except Exception as e:
            print(f"[warn] LLM 精选失败({e}), 回退规则模式")
            picks, noise = rule_pick(d, profile)
            mode = "规则回退"
    else:
        picks, noise = rule_pick(d, profile)
        mode = "规则模式(0 成本)"

    today = datetime.now().strftime("%Y-%m-%d")
    PICKS_JSON.write_text(json.dumps(
        {"date": today, "mode": mode, "picks": picks, "noise_note": noise},
        ensure_ascii=False, indent=2), encoding="utf-8")
    L = []
    A = L.append
    A("# 今日精选 · " + today)
    A("")
    A(f"> 私人编辑 · 画像: {'/'.join(profile.get('purposes', []))} · 模式: {mode} · 数据时间: {d.get('time', '')}")
    A("")
    A(f"## 🎯 值得你看的 {len(picks)} 条")
    A("")
    if not picks:
        A("今日信号中暂未筛出与你画像匹配的内容。")
    for i, p in enumerate(picks, 1):
        A(f"### {i}. [{p.get('domain', '')}] {p.get('title', '')}")
        A("")
        A(f"- **为什么对你有用**: {p.get('reason', '')}")
        A(f"- **可行动作**: {p.get('action', '仅观察')}")
        A(f"- **来源**: {p.get('source', '')} · [阅读原文]({p.get('link', '') or '#'})")
        A("")
    A("## 📉 排除说明")
    A("")
    A(noise or "（无）")
    A("")
    out = REPORTS / f"radar-{today}-picks.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"精选 {len(picks)} 条({mode}) -> {out.name}")


if __name__ == "__main__":
    main()
