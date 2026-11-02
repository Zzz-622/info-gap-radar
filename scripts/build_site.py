#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态网页生成器: 把 reports/ 与 learn/ 的 Markdown 渲染成移动端友好的 HTML 站点。
输出到 radar/docs/ (GitHub Pages 直接托管; 本地双击 docs/index.html 也可预览)。
内置迷你 Markdown 渲染器(覆盖本系统生成文件用到的语法), 仅标准库。
"""
import html as html_mod
import re
import sys
from datetime import datetime
from pathlib import Path

RADAR_ROOT = Path(__file__).resolve().parents[1]
REPORTS = RADAR_ROOT / "reports"
LEARN = RADAR_ROOT / "learn"
CARDS = LEARN / "cards"
TOPICS = LEARN / "topics"
OUT = RADAR_ROOT / "docs"

CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
 max-width:760px;margin:0 auto;padding:14px 16px 40px;line-height:1.75;word-break:break-word}
header h1{font-size:1.35em;margin:8px 0 4px}
nav{margin:6px 0 18px;display:flex;flex-wrap:wrap;gap:6px}
nav a{text-decoration:none;color:#067;border:1px solid #8885;border-radius:14px;padding:2px 12px;font-size:.92em}
nav a.on{background:#067;color:#fff;border-color:#067}
h1{font-size:1.45em;line-height:1.4}
h2{font-size:1.18em;border-bottom:1px solid #8883;padding-bottom:4px;margin:26px 0 10px}
h3{font-size:1.02em;margin:18px 0 6px}
a{color:#0a7}
blockquote{border-left:3px solid #8887;margin:8px 0;padding:2px 12px;color:#888}
li{margin:5px 0}
ul,ol{padding-left:22px}
footer{margin-top:40px;color:#888;font-size:.85em;border-top:1px solid #8883;padding-top:8px}
.meta{color:#888;font-size:.92em}
hr{border:none;border-top:1px solid #8883;margin:18px 0}
"""

NAV = [("index.html", "今日"), ("archive.html", "归档")]


def inline(s):
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def md_to_html(text):
    out = []
    in_list = None  # "ul" or "ol"
    for raw in text.split("\n"):
        line = html_mod.escape(raw).rstrip()
        if not line.strip():
            if in_list:
                out.append(f"</{in_list}>")
                in_list = None
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            if in_list:
                out.append(f"</{in_list}>")
                in_list = None
            lv = len(m.group(1))
            out.append(f"<h{lv}>{inline(m.group(2))}</h{lv}>")
            continue
        if line.startswith("&gt; "):
            if in_list:
                out.append(f"</{in_list}>")
                in_list = None
            out.append(f"<blockquote>{inline(line[5:])}</blockquote>")
            continue
        if re.match(r"^- ", line):
            if in_list != "ul":
                if in_list:
                    out.append(f"</{in_list}>")
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{inline(line[2:])}</li>")
            continue
        m = re.match(r"^(\d+)\.\s+(.*)", line)
        if m:
            if in_list != "ol":
                if in_list:
                    out.append(f"</{in_list}>")
                out.append("<ol>")
                in_list = "ol"
            out.append(f"<li>{inline(m.group(2))}</li>")
            continue
        if re.match(r"^-{3,}$", line):
            if in_list:
                out.append(f"</{in_list}>")
                in_list = None
            out.append("<hr>")
            continue
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None
        out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append(f"</{in_list}>")
    return "\n".join(out)


def page(title, body, depth="", active=""):
    nav = "".join(
        f'<a href="{depth}{u}"{" class=on" if u == active else ""}>{t}</a>' for u, t in NAV)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0a7">
<link rel="manifest" href="{depth}manifest.json">
<link rel="icon" href="{depth}icon.svg">
<title>{title} · 信息差雷达</title>
<style>{CSS}</style></head>
<body>
<header><h1>📡 信息差雷达</h1><nav>{nav}</nav></header>
<main>{body}</main>
<footer>自动生成 · 数据来自公开信息源 · 仅供个人学习研究，不构成投资建议</footer>
</body></html>"""


def slug_date(f):
    m = re.match(r"radar-(\d{4}-\d{2}-\d{2})", f.stem)
    return m.group(1) if m else f.stem


def render_md_file(f, out_rel, depth, heading=None):
    try:
        text = f.read_text(encoding="utf-8")
    except Exception as e:
        text = f"读取失败: {e}"
    title = heading or (f"# {f.stem}" if not text.startswith("#") else "")
    body = md_to_html(title + "\n" + text if title else text)
    (OUT / out_rel).parent.mkdir(parents=True, exist_ok=True)
    (OUT / out_rel).write_text(page(f.stem, body, depth, active="archive.html"), encoding="utf-8")


def main():
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if OUT.exists():
        import shutil
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    reports = sorted(REPORTS.glob("radar-*.md"), reverse=True)
    picks = [f for f in reports if f.name.endswith("-picks.md")]
    weekly = [f for f in reports if f.name.endswith("-weekly.md")]
    daily = [f for f in reports if f not in picks + weekly]
    cards = sorted(CARDS.glob("*.md"), reverse=True) if CARDS.exists() else []

    # 子页面
    for f in daily + weekly:
        render_md_file(f, f"reports/{f.stem}.html", "../")
    for f in picks:
        render_md_file(f, f"picks/{f.stem}.html", "../")
    for f in cards:
        render_md_file(f, f"cards/{f.stem}.html", "../")
    # 主题档案
    topic_rows = []
    for tf in sorted(TOPICS.glob("*/timeline.md")) if TOPICS.exists() else []:
        slug = tf.parent.name
        for name in ("timeline.md", "notes.md", "questions.md"):
            src = tf.parent / name
            if src.exists():
                render_md_file(src, f"topics/{slug}-{name[:-3]}.html", "../")
        topic_rows.append(f'<li><a href="topics/{slug}-timeline.html">{slug} · 时间线</a> · '
                          f'<a href="topics/{slug}-notes.html">机制笔记</a> · '
                          f'<a href="topics/{slug}-questions.html">未解问题</a></li>')

    # 归档页
    def li(f, base):
        return f'<li><a href="{base}/{f.stem}.html">{f.stem}</a></li>'

    arch = ["<h1>归档</h1>"]
    arch.append(f"<h2>📄 日报（{len(daily)}）</h2><ul>")
    arch += [li(f, "reports") for f in daily]
    arch.append("</ul>")
    if weekly:
        arch.append(f"<h2>📆 周报（{len(weekly)}）</h2><ul>")
        arch += [li(f, "reports") for f in weekly]
        arch.append("</ul>")
    arch.append(f"<h2>🎯 精选（{len(picks)}）</h2><ul>")
    arch += [li(f, "picks") for f in picks]
    arch.append("</ul>")
    arch.append(f"<h2>🧠 学习卡（{len(cards)}）</h2><ul>")
    arch += [li(f, "cards") for f in cards]
    arch.append("</ul>")
    if topic_rows:
        arch.append(f"<h2>📚 学习主题（{len(topic_rows)}）</h2><ul>")
        arch += topic_rows
        arch.append("</ul>")
    (OUT / "archive.html").write_text(
        page("归档", "\n".join(arch), active="archive.html"), encoding="utf-8")

    # 首页: 最新精选 + 最新日报 + 最近学习卡
    body = ['<p class="meta">最近更新: ' + datetime.now().strftime("%Y-%m-%d %H:%M") + "</p>"]
    if picks:
        f = picks[0]
        body.append(f"<h2>🎯 今日精选（{f.stem}）</h2>")
        body.append(md_to_html(f.read_text(encoding="utf-8")))
    if daily:
        f = daily[0]
        body.append(f"<h2>📄 最新日报（{f.stem}）</h2>")
        body.append(md_to_html(f.read_text(encoding="utf-8")))
    if cards:
        body.append(f"<h2>🧠 最近学习卡（{min(3, len(cards))} 张）</h2>")
        for f in cards[:3]:
            body.append(md_to_html(f.read_text(encoding="utf-8")))
            body.append("<hr>")
    (OUT / "index.html").write_text(
        page("今日", "\n".join(body), active="index.html"), encoding="utf-8")

    # PWA 附件
    (OUT / "manifest.json").write_text(
        '{"name":"信息差雷达","short_name":"雷达","start_url":".","display":"standalone",'
        '"background_color":"#ffffff","theme_color":"#0a7",'
        '"icons":[{"src":"icon.svg","sizes":"any","type":"image/svg+xml"}]}', encoding="utf-8")
    (OUT / "icon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<circle cx="32" cy="32" r="28" fill="#0a7"/>'
        '<path d="M32 18a14 14 0 0 1 0 28M32 26a6 6 0 0 1 0 12" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/>'
        '<circle cx="32" cy="32" r="3" fill="#fff"/></svg>', encoding="utf-8")

    print(f"站点已生成: {OUT} (index.html + 归档 + {len(daily)} 日报 + {len(picks)} 精选 + {len(cards)} 学习卡)")


if __name__ == "__main__":
    main()
