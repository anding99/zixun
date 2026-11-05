# -*- coding: utf-8 -*-
"""
云版生成器：抓 RSS → 调 DeepSeek（两段式）→ 写 数据/YYYY-MM-DD.json → 跑 build.py → 输出 public/

用法：
  python 云版/generate.py            # 正式：需要 DEEPSEEK_API_KEY
  python 云版/generate.py --dry-run  # 不调模型，用 RSS 生成降级版，验证抓取与构建
"""
import argparse
import concurrent.futures
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "数据"
PUBLIC = ROOT / "public"
CST = timezone(timedelta(hours=8))

API_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions"
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("DW", "https://rss.dw.com/rdf/rss-en-world"),
    ("France 24", "https://www.france24.com/en/rss"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("CNA", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"),
    ("SCMP", "https://www.scmp.com/rss/91/feed"),
    ("Nikkei Asia", "https://asia.nikkei.com/rss/feed/nar"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("Nature", "https://www.nature.com/nature.rss"),
    ("Science News", "https://www.science.org/rss/news_current.xml"),
    ("36Kr", "https://36kr.com/feed"),
    ("中央社", "https://feeds.feedburner.com/rsscna/intworld"),
    ("联合早报", "https://www.zaobao.com.sg/rss/realtime/world"),
]

UA = "Mozilla/5.0 (compatible; ZixunBot/1.0; personal daily digest)"


def clean(text, limit=400):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def parse_feed(raw, source):
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out

    def text_of(node, *names):
        for n in names:
            el = node.find(n)
            if el is not None and el.text:
                return el.text.strip()
        return ""

    items = list(root.iter("item")) or list(root.iter("{http://www.w3.org/2005/Atom}entry"))
    for node in items[:20]:
        title = clean(text_of(node, "title", "{http://www.w3.org/2005/Atom}title"), 160)
        link = text_of(node, "link")
        if not link:
            le = node.find("{http://www.w3.org/2005/Atom}link")
            if le is not None:
                link = le.get("href", "")
        desc = text_of(node, "description", "summary", "{http://www.w3.org/2005/Atom}summary",
                       "{http://purl.org/rss/1.0/modules/content/}encoded")
        date = text_of(node, "pubDate", "{http://www.w3.org/2005/Atom}updated")
        when = None
        if date:
            try:
                when = parsedate_to_datetime(date)
            except Exception:
                try:
                    when = datetime.fromisoformat(date.replace("Z", "+00:00"))
                except Exception:
                    when = None
        if when and when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if not title or not link:
            continue
        out.append({"source": source, "title": title, "text": clean(desc, 320), "url": link, "when": when})
    return out


def collect():
    items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch, url): name for name, url in FEEDS}
        for fut in concurrent.futures.as_completed(futs, timeout=90):
            name = futs[fut]
            try:
                items.extend(parse_feed(fut.result(), name))
            except Exception as exc:  # noqa: BLE001
                print(f"[feed fail] {name}: {exc}", file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=40)
    fresh = [i for i in items if (i["when"] is None or i["when"] >= cutoff)]
    fresh.sort(key=lambda i: i["when"] or datetime.now(timezone.utc), reverse=True)
    seen, out = set(), []
    for i in fresh:
        key = re.sub(r"\W", "", i["title"].lower())[:24]
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out[:50]


def corpus(items):
    lines = []
    for i in items:
        when = i["when"].astimezone(CST).strftime("%m-%d %H:%M") if i["when"] else ""
        lines.append(f"- [{i['source']} {when}] {i['title']}｜{i['text'][:180]}｜{i['url']}")
    return "\n".join(lines)


OVERVIEW_HINT = """{
  "lede": "150-200字",
  "editor_note": "60-100字",
  "brief": ["5条，每条30-45字"],
  "top": [{"kicker":"头条","title":"","summary":"100-150字","points":["三条，每条30-50字"],"source":{"name":"","url":""},"status":""}],
  "regions": [{"name":"美国","en":"United States","summary":"一句话","items":[{"title":"","text":"60-100字","source":{"name":"","url":""}}]}],
  "personal": [{"title":"","text":"70-100字"}],
  "threads": [{"name":"","status":"新增|升级|待验证|证伪|缓和","note":"下一步看什么"}],
  "reading": [{"title":"","outlet":"","note":"","url":""}],
  "sources": ["来源名"]
}"""

SECTIONS_HINT = """{
  "signals": [{"title":"","text":"50-80字","why":"70-100字"}],
  "sections": [{"no":"01","name":"宏观 · 政策","intro":"一句话","items":[{"title":"","text":"60-100字","tag":"","source":{"name":"","url":""}}]}]
}"""

ANALYSIS_HINT = """{
  "analysis": [
    {"kicker":"深度 01 · 政治与资产","title":"","thesis":"一句话论点","body":["4-5段，每段120-170字"],"counter":"70-100字","watch":["3条"]}
  ]
}"""


def overview_prompt(items, prev):
    prev_ctx = ""
    if prev:
        threads = prev.get("threads") or []
        if threads:
            prev_ctx = "上一期线索（今天更新状态）：\n" + "\n".join(
                f"- {t.get('name')}：{t.get('status')}｜{t.get('note')}" for t in threads
            )
    return f"""你是《资讯》个人情报台的主编。今天是 {datetime.now(CST).strftime('%Y-%m-%d')}。
根据素材写今天简报的"总览部分"，只输出 JSON 对象，不要 markdown 代码块。

要求：
1. lede 的第一句必须是一个判断（今天最该记住的一件事），不要罗列新闻标题。
2. 只用素材里出现的链接；不得编造 URL、数字、引语。
2. regions 固定六个、顺序不变：美国/欧洲/中东/亚太/中国/全球南方，每个 2 条。
3. top 恰好 3 条；brief 恰好 5 条；personal 恰好 3 条；threads 3-5 条；reading 3-4 条。
4. 每条写事实与机制，不写"引发关注"。全文中文。总输出不超过 2600 字。

{prev_ctx}

JSON 结构（严格按字段）：
{OVERVIEW_HINT}

素材（{len(items)} 条）：
{corpus(items)}
"""


def sections_prompt(items, overview):
    tops = "\n".join(f"- {t.get('title')}：{t.get('summary')}" for t in (overview.get("top") or []))
    return f"""你在为《资讯》写今天的"行业板块"与"被低估的信号"。只输出 JSON 对象。

今天的主线：
{tops}

要求：
1. sections 固定八个、no 与 name 不变：
   01 宏观 · 政策｜02 市场 · 资产｜03 科技 · AI｜04 产业 · 半导体｜05 能源 · 气候｜06 医药 · 健康｜07 商业 · 公司｜08 科学 · 社会
   每个恰好 2 条。
2. signals 恰好 3 条，每条写清"为什么重要"。
3. 只用素材里出现的链接；不得编造 URL、数字、引语。全文中文。总输出不超过 2600 字。

JSON 结构：
{SECTIONS_HINT}

素材（{len(items)} 条）：
{corpus(items)}
"""


def analysis_prompt(overview):
    tops = "\n".join(f"- {t.get('title')}：{t.get('summary')}" for t in (overview.get("top") or []))
    return f"""你在为《资讯》写今天的三段深读。只输出 JSON 对象。

今天的主线：
{tops}

要求：
1. 三篇的主题必须严格对应，不得跑题：
   - 深度 01 · 政治与资产：选举、地缘、监管如何影响资产定价；
   - 深度 02 · 科技与资本：AI、半导体、平台的资本开支与回报；
   - 深度 03 · 宏观与能源：通胀、央行、油价、财政。即使当天素材偏科技，第三篇也要写成宏观视角，不要写成网络安全。
2. 每篇：thesis 一句话；body 4-5 段，每段 120-170 字，先事实、再机制、再推论；counter 70-100 字；watch 3 条。
3. 不要反复使用"所以呢"这类口头禅，用自然的论证推进；不要每段都以同一句式结尾。
4. 不得编造数字与引语。全文中文。总输出不超过 2600 字。

JSON 结构：
{ANALYSIS_HINT}
"""


def sanitize_urls(obj, known):
    """把不在本次素材里的链接清空，防止编造。"""
    if isinstance(obj, dict):
        u = obj.get("url")
        if isinstance(u, str) and u.startswith("http") and u not in known:
            obj["url"] = ""
        for v in obj.values():
            sanitize_urls(v, known)
    elif isinstance(obj, list):
        for v in obj:
            sanitize_urls(v, known)


def call_api(text, max_tokens=6000):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY")
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是严谨的中文财经与地缘编辑，只输出合法 JSON，不输出其他文字。"},
            {"role": "user", "content": text},
        ],
        "temperature": 0.6,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=300) as r:
        payload = json.loads(r.read().decode("utf-8"))
    choice = payload["choices"][0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError("输出被截断（finish_reason=length）")
    return json.loads(choice["message"]["content"])


REQUIRED = ["lede", "brief", "top", "regions"]


def validate_overview(obj):
    missing = [k for k in REQUIRED if not obj.get(k)]
    if missing:
        raise ValueError("缺字段: " + ",".join(missing))
    if len(obj["top"]) < 3:
        raise ValueError("top 少于 3 条")
    if len(obj["regions"]) < 6:
        raise ValueError("regions 少于 6 个")
    return obj


def validate_sections(obj):
    if len(obj.get("sections") or []) < 8:
        raise ValueError("sections 少于 8 个")
    if len(obj.get("signals") or []) < 3:
        raise ValueError("signals 少于 3 条")
    return obj


def fallback(items, date, issue):
    top = items[:10]
    return {
        "date": date, "weekday": "星期" + "一二三四五六日"[datetime.strptime(date, "%Y-%m-%d").weekday()],
        "issue": issue, "edition": "晨刊",
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "tagline": "一个人读的全球情报简报",
        "lede": "今天的自动写稿没有完成，这是一份由原始标题生成的降级版：只保留事实与链接，不做分析。完整版会在下一次成功运行时恢复。",
        "editor_note": "降级版：只列出过去 40 小时里最重要的国际报道，按时间排序。",
        "brief": [f"{i['source']}：{i['title']}"[:60] for i in top[:5]],
        "ticker": [],
        "top": [{
            "kicker": "要闻", "title": i["title"], "summary": i["text"][:160] or i["title"],
            "points": [], "source": {"name": i["source"], "url": i["url"]}, "status": "原始报道",
        } for i in top[:3]],
        "regions": [], "signals": [],
        "sections": [{
            "no": "01", "name": "今日要闻", "intro": "按发布时间排序的原始报道。",
            "items": [{"title": i["title"], "text": i["text"][:180], "tag": i["source"],
                       "source": {"name": i["source"], "url": i["url"]}} for i in top],
        }],
        "analysis": [], "personal": [], "threads": [],
        "numbers": {"rows": [], "note": "降级版不含行情数据。"},
        "calendar": [],
        "reading": [{"title": i["title"], "outlet": i["source"], "note": i["text"][:100], "url": i["url"]} for i in top[:4]],
        "sources": sorted({i["source"] for i in top}),
    }


def next_issue(date):
    issues = []
    for p in DATA.glob("*.json"):
        try:
            issues.append(int(json.loads(p.read_text(encoding="utf-8")).get("issue", 0)))
        except Exception:
            pass
    return (max(issues) if issues else 0) + 1


def previous_edition():
    files = sorted(DATA.glob("*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def build():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo and "SITE_URL" not in os.environ:
        owner, name = repo.split("/", 1)
        os.environ["SITE_URL"] = (
            f"https://{owner.lower()}.github.io/" if name.lower() == f"{owner.lower()}.github.io"
            else f"https://{owner.lower()}.github.io/{name}/"
        )
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True, cwd=str(ROOT))
    src = ROOT / "站点"
    if PUBLIC.exists():
        for p in PUBLIC.rglob("*"):
            if p.is_file():
                p.unlink()
    PUBLIC.mkdir(exist_ok=True)
    for p in src.rglob("*"):
        if p.is_file():
            rel = p.relative_to(src)
            dst = PUBLIC / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(p.read_bytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=datetime.now(CST).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    items = collect()
    print(f"抓到 {len(items)} 条素材")
    if not items:
        print("没有素材，放弃", file=sys.stderr)
        return 1

    issue = next_issue(args.date)
    known = {i["url"] for i in items}
    data = None
    if not args.dry_run:
        for attempt in (1, 2):
            try:
                data = validate_overview(call_api(overview_prompt(items, previous_edition()), 5000))
                sanitize_urls(data, known)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"[总览段失败 {attempt}] {exc}", file=sys.stderr)
        if data:
            for attempt in (1, 2):
                try:
                    extra = validate_sections(call_api(sections_prompt(items, data), 5000))
                    sanitize_urls(extra, known)
                    data["sections"] = extra.get("sections", [])
                    data["signals"] = extra.get("signals", [])
                    break
                except Exception as exc:  # noqa: BLE001
                    print(f"[板块段失败 {attempt}] {exc}", file=sys.stderr)
            data.setdefault("sections", [])
            data.setdefault("signals", [])
            for attempt in (1, 2):
                try:
                    analysis = call_api(analysis_prompt(data), 4000)
                    if analysis.get("analysis"):
                        data["analysis"] = analysis["analysis"]
                    break
                except Exception as exc:  # noqa: BLE001
                    print(f"[深读段失败 {attempt}] {exc}", file=sys.stderr)
            data.setdefault("analysis", [])
    if not data:
        data = fallback(items, args.date, issue)

    data.setdefault("date", args.date)
    data.setdefault("issue", issue)
    data.setdefault("edition", "晨刊")
    data.setdefault("generated_at", datetime.now(CST).isoformat(timespec="seconds"))
    data.setdefault("weekday", "星期" + "一二三四五六日"[datetime.strptime(args.date, "%Y-%m-%d").weekday()])
    data.setdefault("tagline", "一个人读的全球情报简报")
    data.setdefault("numbers", {"rows": [], "note": ""})
    data.setdefault("calendar", [])
    data.setdefault("reading", [])
    data.setdefault("sources", [])
    data.setdefault("ticker", [])

    out = DATA / f"{args.date}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 {out}")

    build()
    print(f"已生成 public/，第{data['issue']:03d}期，深读 {len(data.get('analysis', []))} 篇")
    return 0


if __name__ == "__main__":
    sys.exit(main())
