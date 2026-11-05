#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资讯 · 个人情报台 —— 静态站生成器
用法:  python build.py
输入:  数据/YYYY-MM-DD.json
输出:  站点/index.html（最新一期）、站点/YYYY-MM-DD.html、站点/archive.html、
       站点/feed.xml、推送/YYYY-MM-DD.txt
"""
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "数据"
SITE = ROOT / "站点"
RES = ROOT / "资源"
PUSH = ROOT / "推送"

CSS = (RES / "style.css").read_text(encoding="utf-8")
JS = (RES / "app.js").read_text(encoding="utf-8")

SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8790").rstrip("/")


def e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def rich(value):
    """只允许 **加粗** 这一种行内标记。"""
    text = e(value)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def cls(direction):
    return "up" if direction == "up" else ("down" if direction == "down" else "")


def arrow(direction):
    return "▲" if direction == "up" else ("▼" if direction == "down" else "•")


def reading_time(data):
    chars = len(str(data.get("lede", "")))
    for t in data.get("top", []):
        chars += len(str(t.get("summary", ""))) + sum(len(str(p)) for p in t.get("points", []))
    for r in data.get("regions", []):
        chars += sum(len(str(i.get("text", ""))) + len(str(i.get("title", ""))) for i in r.get("items", []))
    for s in data.get("sections", []):
        chars += sum(len(str(i.get("text", ""))) + len(str(i.get("title", ""))) for i in s.get("items", []))
    for a in data.get("analysis", []):
        chars += len(str(a.get("thesis", ""))) + sum(len(str(p)) for p in a.get("body", []))
    chars += sum(len(str(x)) for x in data.get("brief", []))
    for s in data.get("signals", []):
        chars += len(str(s.get("title", ""))) + len(str(s.get("text", ""))) + len(str(s.get("why", "")))
    for p in data.get("personal", []):
        chars += len(str(p.get("text", "")))
    for t in data.get("threads", []):
        chars += len(str(t.get("note", ""))) + 20
    return max(1, round(chars / 420))


def load():
    editions = []
    for path in sorted(DATA.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[跳过] {path.name}: {exc}")
            continue
        data.setdefault("date", path.stem)
        data["_path"] = path
        editions.append(data)
    editions.sort(key=lambda d: d["date"], reverse=True)
    return editions


def head(data, page_title, description, canonical):
    return f"""<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(page_title)}</title>
<meta name="description" content="{e(description[:150])}">
<meta name="color-scheme" content="light dark">
<meta property="og:title" content="{e(page_title)}">
<meta property="og:description" content="{e(description[:150])}">
<meta property="og:type" content="article">
<link rel="alternate" type="application/atom+xml" title="资讯 · 每日更新" href="feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23a8382a'/%3E%3Ctext x='16' y='23' font-size='19' text-anchor='middle' fill='%23f7f3ea' font-family='serif'%3E%E8%AE%AF%3C/text%3E%3C/svg%3E">
<style>
{CSS}
</style>
</head>"""


def topbar(data, archive=True):
    date = e(data["date"])
    prev = data.get("_prev")
    nxt = data.get("_next")
    nav_prev = f'<a href="{prev["date"]}.html" title="上一期">← 上一期</a>' if prev else "<span></span>"
    nav_next = f'<a href="{nxt["date"]}.html" title="下一期">下一期 →</a>' if nxt else "<span></span>"
    arch = '<a href="archive.html">往期</a>' if archive else '<a href="index.html">今日</a>'
    return f"""<div class="progress" id="progress"></div>
<header class="topbar">
  <div class="topbar-in">
    <span class="brand">资<i>·</i>讯</span>
    <span>{date}</span>
    <span class="spacer"></span>
    {nav_prev}
    {nav_next}
    {arch}
    <a href="feed.xml" title="订阅">RSS</a>
    <button class="icon-btn" id="copy-btn" title="复制本页链接">⧉</button>
    <button class="icon-btn" id="theme-btn" title="切换深浅色" aria-label="切换深浅色">☾</button>
  </div>
</header>"""


def masthead(data):
    return f"""<div class="masthead">
  <div class="eyebrow"><span>PERSONAL INTELLIGENCE</span><span class="line"></span><span>{e(data.get('edition', '晨刊'))}</span></div>
  <h1>资讯<small>每 日 全 球 情 报 简 报</small></h1>
  <div class="masthead-meta">
    <span class="date">{e(data['date'])}　{e(data.get('weekday', ''))}</span>
    <span class="issue">第 {int(data.get('issue', 1)):03d} 期</span>
    <span>约 {reading_time(data)} 分钟</span>
    <span class="tagline">{e(data.get('tagline', ''))}</span>
  </div>
</div>"""


def ticker(data):
    rows = data.get("ticker") or []
    if not rows:
        return ""
    out = []
    for t in rows:
        val = f'<span class="t-val">{e(t.get("value"))}</span>' if t.get("value") else ""
        out.append(
            f'<span class="tick"><span class="t-label">{e(t.get("label"))}</span>{val}'
            f'<span class="t-chg {cls(t.get("dir"))}">{arrow(t.get("dir"))} {e(t.get("change"))}</span></span>'
        )
    return f'<div class="ticker-wrap"><div class="ticker">{"".join(out)}</div></div>'


def lede(data):
    note = data.get("editor_note")
    note_html = f'<p class="note">{rich(note)}</p>' if note else ""
    return f"""<section class="lede">
  <p>{rich(data.get('lede', ''))}</p>
  {note_html}
</section>"""


def hero(data):
    tops = data.get("top") or []
    if not tops:
        return ""
    first = tops[0]
    points = "".join(f"<li>{rich(p)}</li>" for p in first.get("points", []))
    src = first.get("source") or {}
    status = f'<span class="tag">{e(first.get("status"))}</span>' if first.get("status") else ""
    main = f"""<div class="hero-main">
    <span class="kicker">{e(first.get('kicker', '头条'))}</span>
    <h2>{rich(first.get('title'))}</h2>
    <p class="dek">{rich(first.get('summary'))}</p>
    <ul>{points}</ul>
    <div class="meta">{status}<a class="src" href="{e(src.get('url') or '#')}" target="_blank" rel="noopener">{e(src.get('name', ''))} ↗</a></div>
  </div>"""

    side = []
    for t in tops[1:]:
        s = t.get("source") or {}
        side.append(f"""<div class="item">
      <span class="kicker">{e(t.get('kicker', ''))}</span>
      <h3>{rich(t.get('title'))}</h3>
      <p>{rich(t.get('summary'))}</p>
      <a class="src" href="{e(s.get('url', '#'))}" target="_blank" rel="noopener">{e(s.get('name', ''))} ↗</a>
    </div>""")
    return f'<section class="hero">{main}<div class="hero-side">{"".join(side)}</div></section>'


def brief_block(data):
    items = data.get("brief") or []
    if not items:
        return ""
    lis = "".join(
        f'<li><b>{i:02d}</b><span>{rich(t)}</span></li>' for i, t in enumerate(items, 1)
    )
    return f"""<section class="brief" id="brief">
  <p class="brief-label">三分钟速览 · In Brief</p>
  <ol class="brief-list">{lis}</ol>
</section>"""


def signals_block(data):
    items = data.get("signals") or []
    if not items:
        return ""
    cards = []
    for i, s in enumerate(items, 1):
        cards.append(f"""<article class="signal">
      <div class="idx">{i:02d}</div>
      <h3>{rich(s.get('title'))}</h3>
      <p>{rich(s.get('text'))}</p>
      <p class="why"><b>为什么重要</b>　{rich(s.get('why'))}</p>
    </article>""")
    return f"""<section class="block" id="signals">
  <div class="block-head"><span class="no">SIG</span><h2>被低估的信号</h2>
    <p class="intro">三条没上头条、但会改变判断的细节。信号不等于结论，标注了它可能错在哪。</p></div>
  <div class="signals">{"".join(cards)}</div>
</section>"""


def personal_block(data):
    items = data.get("personal") or []
    if not items:
        return ""
    cards = "".join(
        f'<article class="pcard"><h3>{rich(i.get("title"))}</h3><p>{rich(i.get("text"))}</p></article>'
        for i in items
    )
    return f"""<section class="block" id="personal">
  <div class="block-head"><span class="no">YOU</span><h2>与你有关</h2>
    <p class="intro">把宏观翻译成个人决策：换汇、房贷、工作。只谈机制，不给建议。</p></div>
  <div class="personal">{cards}</div>
</section>"""


def threads_block(data):
    items = data.get("threads") or []
    if not items:
        return ""
    chips = {"新增": "new", "升级": "up", "待验证": "watch", "证伪": "dead", "缓和": "dead"}
    rows = "".join(
        f'<tr><td>{e(t.get("name"))}</td>'
        f'<td><span class="chip {chips.get(t.get("status"), "")}">{e(t.get("status"))}</span></td>'
        f'<td class="note-cell">{rich(t.get("note"))}</td></tr>'
        for t in items
    )
    return f"""<section class="block" id="threads">
  <div class="block-head"><span class="no">THREAD</span><h2>线索追踪</h2>
    <p class="intro">昨天的问题，今天有没有答案。状态：新增 / 升级 / 待验证 / 证伪。</p></div>
  <table class="data threads">
    <thead><tr><th style="width:22%">线索</th><th style="width:16%">状态</th><th>下一步看什么</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def regions_block(data):
    regions = data.get("regions") or []
    if not regions:
        return ""
    cards = []
    for r in regions:
        items = "".join(
            f'<div class="ritem"><h4>{rich(i.get("title"))}</h4><p>{rich(i.get("text"))}</p></div>'
            for i in r.get("items", [])
        )
        cards.append(f"""<article class="region">
      <header><h3>{e(r.get('name'))}</h3><span class="en">{e(r.get('en', ''))}</span></header>
      <p class="r-sum">{rich(r.get('summary'))}</p>
      {items}
    </article>""")
    return f"""<section class="block" id="world">
  <div class="block-head"><span class="no">00</span><h2>全球扫描</h2>
    <p class="intro">六个区域，各取当天最值得知道的两三件事。不追求齐全，只保留会改变判断的部分。</p></div>
  <div class="regions">{"".join(cards)}</div>
</section>"""


def sections_block(data):
    out = []
    for s in data.get("sections") or []:
        items = []
        for i in s.get("items", []):
            src = i.get("source") or {}
            tag = f'<span class="tag">{e(i.get("tag"))}</span>' if i.get("tag") else ""
            link = (
                f'<a class="src" href="{e(src.get("url"))}" target="_blank" rel="noopener">{e(src.get("name"))} ↗</a>'
                if src.get("url")
                else f'<span class="src">{e(src.get("name"))}</span>'
            )
            items.append(f"""<article class="entry">
      <h3>{rich(i.get('title'))}</h3>
      <p>{rich(i.get('text'))}</p>
      <div class="meta">{tag}{link}</div>
    </article>""")
        anchor = f"s{str(s.get('no', '')).zfill(2)}"
        out.append(f"""<section class="block" id="{anchor}">
  <div class="block-head"><span class="no">{e(s.get('no'))}</span><h2>{e(s.get('name'))}</h2>
    <p class="intro">{rich(s.get('intro'))}</p></div>
  <div class="items">{"".join(items)}</div>
</section>""")
    return "\n".join(out)


def analysis_block(data):
    items = data.get("analysis") or []
    if not items:
        return ""
    body = []
    for a in items:
        paras = "".join(f"<p>{rich(p)}</p>" for p in a.get("body", []))
        watch = "".join(f"<li>{rich(w)}</li>" for w in a.get("watch", []))
        watch_html = (
            f'<p class="watch-label">接下来盯什么</p><ul class="watch">{watch}</ul>' if watch else ""
        )
        counter = (
            f'<div class="counter"><b>反方</b>　{rich(a.get("counter"))}</div>' if a.get("counter") else ""
        )
        body.append(f"""<article class="analysis">
    <span class="kicker">{e(a.get('kicker', '深度'))}</span>
    <h3>{rich(a.get('title'))}</h3>
    <p class="thesis">{rich(a.get('thesis'))}</p>
    <div class="body">{paras}</div>
    {counter}
    {watch_html}
  </article>""")
    return f"""<section class="deep" id="deep">
  <div class="block-head"><span class="no">DEEP</span><h2>三段深读</h2>
    <p class="intro">每篇都给论点、证据、反方与观察点。观点可以不同意，事实必须可核对。</p></div>
  {"".join(body)}
</section>"""


def numbers_block(data):
    num = data.get("numbers") or {}
    rows = num.get("rows") or []
    trs = "".join(
        f'<tr><td>{e(r.get("label"))}</td><td class="num">{e(r.get("value"))}</td>'
        f'<td class="chg {cls(r.get("dir"))}">{e(r.get("change"))}</td></tr>'
        for r in rows
    )
    note = f'<p class="data-note">{rich(num.get("note"))}</p>' if num.get("note") else ""
    cal = data.get("calendar") or []
    cal_html = "".join(
        f'<li><time>{e(c.get("time"))}</time><span>{rich(c.get("event"))}</span></li>' for c in cal
    )
    cal_block = (
        f'<div><p class="mini-head">今日日程 · Calendar</p>'
        f'<ul class="cal">{cal_html}</ul></div>'
        if cal
        else ""
    )
    return f"""<section class="block" id="data">
  <div class="block-head"><span class="no">DATA</span><h2>数字与日程</h2>
    <p class="intro">收盘价、收益率与今日待发布数据。口径不一致的地方，正文里已经写明。</p></div>
  <div class="panel-grid">
    <div>
      <table class="data">
        <thead><tr><th>标的</th><th style="text-align:right">最新</th><th style="text-align:right">涨跌</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
      {note}
    </div>
    {cal_block}
  </div>
</section>"""


def reading_block(data):
    rows = data.get("reading") or []
    if not rows:
        return ""
    cards = "".join(
        f"""<a class="read" href="{e(r.get('url', '#'))}" target="_blank" rel="noopener">
      <span class="r-out">{e(r.get('outlet'))}</span>
      <h3>{rich(r.get('title'))}</h3>
      <p>{rich(r.get('note'))}</p>
    </a>"""
        for r in rows
    )
    return f"""<section class="block" id="reading">
  <div class="block-head"><span class="no">READ</span><h2>延伸阅读</h2>
    <p class="intro">如果你想回到原始材料，从这里开始。</p></div>
  <div class="reading">{cards}</div>
</section>"""


def nav(data):
    items = ['<a href="#world">全球扫描</a>', '<a href="#signals">信号</a>']
    for s in data.get("sections") or []:
        anchor = f"s{str(s.get('no', '')).zfill(2)}"
        items.append(f'<a href="#{anchor}">{e(s.get("name"))}</a>')
    items.append('<a href="#deep">深读</a>')
    items.append('<a href="#personal">与你</a>')
    items.append('<a href="#threads">线索</a>')
    items.append('<a href="#data">数据</a>')
    items.append('<a href="#reading">阅读</a>')
    return f'<nav class="nav"><div class="nav-in">{"".join(items)}</div></nav>'


def footer(data):
    srcs = "".join(f"<span>{e(s)}</span>" for s in data.get("sources", []))
    pub = data.get("_public_url")
    pub_html = (
        f'<br>手机 / 公网：<a href="{e(pub)}" target="_blank" rel="noopener">{e(pub)}</a>'
        if pub
        else ""
    )
    prev = data.get("_prev")
    nxt = data.get("_next")
    pager = "<div class=\"pager\">"
    pager += f'<a href="{prev["date"]}.html">← {prev["date"]}</a>' if prev else "<span></span>"
    pager += '<a href="archive.html">全部往期</a>'
    pager += f'<a href="{nxt["date"]}.html">{nxt["date"]} →</a>' if nxt else "<span></span>"
    pager += "</div>"
    return f"""{pager}
<footer class="footer">
  <div class="footer-in">
    <div>
      <h4>Sources</h4>
      <div class="srcs">{srcs}</div>
    </div>
    <div class="fine">
      <h4>说明</h4>
      生成时间 {e(data.get('generated_at', ''))}　·　第 {int(data.get('issue', 1)):03d} 期{pub_html}<br>
      价格为公开报道口径，可能因结算价与收盘价取样时点不同而存在差异；带「传闻」「待官宣」标记的内容尚未被官方确认。<br>
      本页为个人学习用途的信息整理，不构成投资建议。键盘 ← → 可翻页。
    </div>
  </div>
</footer>
<a id="to-top" href="#" title="回到顶部" style="position:fixed;right:18px;bottom:18px;width:38px;height:38px;display:flex;align-items:center;justify-content:center;border:1px solid var(--rule-strong);background:var(--paper);color:var(--muted);opacity:0;transition:opacity .2s;z-index:50">↑</a>"""


def render_edition(data):
    desc = data.get("lede", "")
    title = f"资讯 · {data['date']} · 第{int(data.get('issue', 1)):03d}期"
    prev = data.get("_prev")
    nxt = data.get("_next")
    body_attrs = (
        f'data-prev="{prev["date"]}.html"' if prev else 'data-prev=""'
    ) + " " + (f'data-next="{nxt["date"]}.html"' if nxt else 'data-next=""')
    parts = [
        head(data, title, desc, f"{data['date']}.html"),
        f'<body {body_attrs}>',
        topbar(data),
        masthead(data),
        ticker(data),
        lede(data),
        brief_block(data),
        hero(data),
        nav(data),
        regions_block(data),
        signals_block(data),
        sections_block(data),
        analysis_block(data),
        personal_block(data),
        threads_block(data),
        numbers_block(data),
        reading_block(data),
        footer(data),
        f"<script>{JS}</script>",
        "</body></html>",
    ]
    return "\n".join(p for p in parts if p)


def render_archive(editions):
    rows = []
    for d in editions:
        top = (d.get("top") or [{}])[0]
        rows.append(f"""<a class="arch-item" href="{d['date']}.html">
    <span class="arch-date">{e(d['date'])}<br><span style="opacity:.6">{e(d.get('weekday', ''))}</span></span>
    <span><h3>{rich(top.get('title', d.get('lede', '')))}</h3><p>{rich(d.get('lede', ''))}</p></span>
    <span class="arch-no">第 {int(d.get('issue', 1)):03d} 期</span>
  </a>""")
    body = "".join(rows) if rows else '<p class="empty">还没有往期。今天之后，这里会长出时间线。</p>'
    return "\n".join([
        f"""<!doctype html>
<html lang="zh-CN" data-theme="light">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>往期 · 资讯</title><meta name="color-scheme" content="light dark">
<link rel="alternate" type="application/atom+xml" title="资讯 · 每日更新" href="feed.xml">
<style>
{CSS}
</style></head>
<body>""",
        """<header class="topbar"><div class="topbar-in"><span class="brand">资<i>·</i>讯</span><span>往期</span>
<span class="spacer"></span><a href="index.html">今日</a><a href="feed.xml">RSS</a>
<button class="icon-btn" id="theme-btn">☾</button></div></header>""",
        """<div class="masthead"><div class="eyebrow"><span>ARCHIVE</span><span class="line"></span><span>全部期号</span></div>
<h1>往期<small>时 间 是 最 好 的 编 辑</small></h1>
<div class="masthead-meta"><span class="date">共 %d 期</span><span class="tagline">按时间倒序</span></div></div>""" % len(editions),
        f'<main class="archive">{body}</main>',
        f"<script>{JS}</script></body></html>",
    ])


def render_feed(editions):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    entries = []
    for d in editions[:30]:
        link = f"{SITE_URL}/{d['date']}.html"
        summary = e(d.get("lede", ""))
        entries.append(f"""  <entry>
    <title>{e('第%03d期 · %s' % (int(d.get('issue', 1)), d['date']))}</title>
    <link href="{link}"/>
    <id>{link}</id>
    <updated>{d['date']}T07:30:00+08:00</updated>
    <summary type="html">{summary}</summary>
  </entry>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>资讯 · 个人情报台</title>
  <subtitle>每天一份，全球视野与深度分析</subtitle>
  <link href="{SITE_URL}/feed.xml" rel="self"/>
  <link href="{SITE_URL}/"/>
  <id>{SITE_URL}/</id>
  <updated>{now}</updated>
  <author><name>个人情报台</name></author>
{chr(10).join(entries)}
</feed>
"""


def render_push(data):
    tops = data.get("top") or []
    head_line = f"【资讯 · 第{int(data.get('issue', 1)):03d}期】{data['date']} {data.get('weekday', '')}"
    lines = [head_line, "", data.get("lede", ""), ""]
    for i, t in enumerate(tops[:2], 1):
        lines.append(f"■ {t.get('kicker', '')}｜{t.get('title', '')}")
        lines.append(f"  {t.get('summary', '')}")
        lines.append("")
    for a in (data.get("analysis") or [])[:1]:
        lines.append(f"■ 深读｜{a.get('title', '')}")
        lines.append(f"  {a.get('thesis', '')}")
        lines.append("")
    lines.append(f"全文与往期：{SITE_URL}/{data['date']}.html")
    lines.append("（个人学习用途的信息整理，不构成投资建议）")
    return "\n".join(lines)


def main():
    SITE.mkdir(exist_ok=True)
    PUSH.mkdir(exist_ok=True)
    editions = load()
    if not editions:
        print("数据目录为空，没有任何一期。")
        return 1

    public_url = ""
    pub_file = ROOT / "公网链接.txt"
    if pub_file.exists():
        public_url = pub_file.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
    for d in editions:
        d["_public_url"] = public_url

    for i, d in enumerate(editions):
        d["_prev"] = editions[i + 1] if i + 1 < len(editions) else None   # 更早的一期
        d["_next"] = editions[i - 1] if i - 1 >= 0 else None            # 更新的一期

    for d in editions:
        (SITE / f"{d['date']}.html").write_text(render_edition(d), encoding="utf-8")
        (PUSH / f"{d['date']}.txt").write_text(render_push(d), encoding="utf-8")

    latest = editions[0]
    (SITE / "index.html").write_text(render_edition(latest), encoding="utf-8")
    (SITE / "archive.html").write_text(render_archive(editions), encoding="utf-8")
    (SITE / "feed.xml").write_text(render_feed(editions), encoding="utf-8")

    print(f"已生成 {len(editions)} 期")
    print(f"最新：{latest['date']} 第{int(latest.get('issue', 1)):03d}期 → 站点/index.html")
    print(f"链接（服务启动后）：{SITE_URL}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
