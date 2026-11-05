# -*- coding: utf-8 -*-
"""
《世界课》静态页生成器
输入：世界课/数据/YYYY-MM-DD.json
输出：站点/world/index.html、站点/world/YYYY-MM-DD.html、站点/world/archive.html
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WDATA = ROOT / "世界课" / "数据"
OUT = ROOT / "站点" / "world"
CSS = (ROOT / "世界课" / "资源" / "world.css").read_text(encoding="utf-8")

WEEKDAY_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def e(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def rich(v):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", e(v))


def load():
    items = []
    for p in sorted(WDATA.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d.setdefault("date", p.stem)
            items.append(d)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {p.name}: {exc}", file=sys.stderr)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def head(d, title):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(d.get('question', ''))}">
<meta property="og:title" content="{e(title)}">
<style>
{CSS}
.arch{{max-width:760px;margin:0 auto;padding:0 26px 60px}}
.arch a{{display:block;padding:18px 0;border-bottom:1px solid var(--rule);border-left:none}}
.arch a:hover{{background:var(--paper2)}}
.arch .d{{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.08em}}
.arch .q{{font-family:var(--serif);font-size:19px;line-height:1.6;margin:4px 0 2px;color:var(--ink)}}
.arch .t{{font-size:12.5px;color:var(--muted)}}
</style>
</head>"""


def topbar(d, prev, nxt):
    p = f'<a href="{prev["date"]}.html">← 上一课</a>' if prev else "<span></span>"
    n = f'<a href="{nxt["date"]}.html">下一课 →</a>' if nxt else "<span></span>"
    return f"""<div class="topbar"><div class="in">
  <b>世界课</b><span>每日一课</span><span class="sp"></span>
  {p}{n}<a href="archive.html">往期</a>
  <span>第 {int(d.get('issue', 1)):03d} 课</span><span>{e(d['date'])}</span>
</div></div>"""


def body_paras(paras):
    out = []
    for i, p in enumerate(paras):
        text = str(p)
        if i == 0 and text and "\u4e00" <= text[0] <= "\u9fff":
            out.append(f'<p><span class="dropcap">{e(text[0])}</span>{rich(text[1:])}</p>')
        else:
            out.append(f"<p>{rich(text)}</p>")
    return "".join(out)


def render(d, prev, nxt):
    col = d.get("column") or {}
    world = d.get("world") or {}
    kid = d.get("kid") or {}
    body = body_paras(col.get("body", []))
    pull = f'<div class="pull">{rich(col.get("pull"))}</div>' if col.get("pull") else ""
    counter = f'<div class="counter"><b>反方 · 最强的那个版本</b>{rich(d.get("counter"))}</div>' if d.get("counter") else ""
    world_html = ""
    if world.get("title"):
        paras = "".join(f"<p>{rich(p)}</p>" for p in world.get("paras", []))
        miss = f'<div class="miss"><b>被忽略的一点</b>{rich(world.get("miss"))}</div>' if world.get("miss") else ""
        world_html = f"""<section class="world">
  <div class="w-label"><span>World Watch · 世界观察</span><span class="date">{e(d['date'])}</span></div>
  <h3>{rich(world.get('title'))}</h3>
  {paras}
  {miss}
</section>"""
    qs = "".join(f"<li>{rich(q)}</li>" for q in kid.get("questions", []))
    exp = f'<div class="exp"><b>一个五分钟的小实验</b>：{rich(kid.get("experiment"))}</div>' if kid.get("experiment") else ""
    kid_html = f"""<section class="kid">
  <div class="k-label">For a nine-year-old · 今晚可以问的三个问题</div>
  <h3>不用讲道理，只问他怎么看</h3>
  <ol>{qs}</ol>
  {exp}
</section>""" if qs else ""
    reads = "".join(f"""<li>
      <span class="out">{e(r.get('out'))}</span>
      <a class="rt" href="{e(r.get('url') or '#')}" target="_blank" rel="noopener">{rich(r.get('title'))}</a>
      <span class="rn">{rich(r.get('note'))}</span>
    </li>""" for r in d.get("reading", []))
    reading_html = f'<section class="reading"><h3 class="label">Read · 延伸</h3><ul>{reads}</ul></section>' if reads else ""
    threads = "".join(f"<li>{rich(t)}</li>" for t in d.get("threads", []))
    threads_html = f'<div class="threads"><h3>长期线索 · 值得盯几年</h3><ul>{threads}</ul></div>' if threads else ""

    title = f"世界课 · 第{int(d.get('issue', 1)):03d}课 · {d.get('question', '')}"
    return "\n".join([
        head(d, title),
        f"<body>{topbar(d, prev, nxt)}<div class=\"wrap\">",
        f"""<header class="mast">
  <div class="eyebrow"><span>WORLD LESSONS · FOR A CURIOUS NINE-YEAR-OLD</span></div>
  <h1>世界课</h1>
  <div class="sub">给 父 与 子 的 每 日 一 课</div>
  <div class="meta">
    <span>{e(d['date'])}　{e(d.get('weekday', ''))}</span>
    <span class="no">第 {int(d.get('issue', 1)):03d} 课</span>
    <span>约 {int(d.get('minutes', 8))} 分钟</span>
    <span class="week">第 {int(d.get('week', 1)):02d} 周 · {e(d.get('theme', ''))}</span>
  </div>
  <div class="weekbar"><b>本周主题：{e(d.get('theme', ''))}</b>　{rich(d.get('theme_note', ''))}</div>
</header>""",
        f"""<div class="question">
  <div class="q-label">今日一问 · {WEEKDAY_EN[int(d.get('weekday_index', 3))]} , {e(col.get('kind', ''))}</div>
  <h2>{rich(d.get('question'))}</h2>
  <p class="answer">{rich(d.get('answer'))}</p>
</div>""",
        f"""<section>
  <h3 class="label">{e(col.get('kind', ''))} · {e(col.get('kind_en', ''))}</h3>
  <h2 class="title">{rich(col.get('title'))}</h2>
  <div class="body">{body}</div>
  {pull}
  {counter}
</section>""",
        world_html,
        kid_html,
        reading_html,
        threads_html,
        f"""<footer><div class="fine">
    <span>世界课 · 第 {int(d.get('issue', 1)):03d} 课 · {e(d['date'])}</span>
    <span>事实 / 推断 / 猜测，三种语气已尽量分开。不构成任何建议。</span>
  </div></footer>""",
        "</div></body></html>",
    ])


def render_archive(items):
    rows = "".join(f"""<a href="{d['date']}.html">
  <div class="d">{e(d['date'])}　第 {int(d.get('issue', 1)):03d} 课</div>
  <div class="q">{rich(d.get('question'))}</div>
  <div class="t">第 {int(d.get('week', 1)):02d} 周 · {e(d.get('theme', ''))}</div>
</a>""" for d in items)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>往期 · 世界课</title>
<style>{CSS}</style></head><body>
<div class="topbar"><div class="in"><b>世界课</b><span>往期</span><span class="sp"></span><a href="index.html">今日</a></div></div>
<div class="wrap"><header class="mast"><div class="eyebrow"><span>ARCHIVE · ALL LESSONS</span></div>
<h1>往期</h1><div class="sub">一 年 五 十 二 个 主 题</div>
<div class="meta"><span>共 {len(items)} 课</span><span class="week">按时间倒序</span></div></header></div>
<div class="arch">{rows}</div>
</body></html>"""


def main():
    items = load()
    if not items:
        print("世界课暂无数据")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for i, d in enumerate(items):
        prev = items[i + 1] if i + 1 < len(items) else None
        nxt = items[i - 1] if i > 0 else None
        (OUT / f"{d['date']}.html").write_text(render(d, prev, nxt), encoding="utf-8")
    (OUT / "index.html").write_text(render(items[0], items[1] if len(items) > 1 else None, None), encoding="utf-8")
    (OUT / "archive.html").write_text(render_archive(items), encoding="utf-8")
    print(f"世界课：{len(items)} 课，最新 {items[0]['date']} 第{int(items[0].get('issue', 1)):03d}课")
    return 0


if __name__ == "__main__":
    sys.exit(main())
