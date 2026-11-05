# -*- coding: utf-8 -*-
"""
《世界课》云端生成器：RSS → DeepSeek → 世界课/数据/YYYY-MM-DD.json → 构建并发布
用法：
  python 云版/generate_world.py
  python 云版/generate_world.py --dry-run
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import generate as base  # noqa: E402
import publish  # noqa: E402

WDATA = ROOT / "世界课" / "数据"

THEMES = [
    ("稀缺与选择", "钱、时间、注意力都不够用。经济学不是关于钱，是关于“不够用的时候怎么办”。这一周，我们看五种“不够用”。"),
    ("因果与相关", "两件事一起发生，不等于一件导致了另一件。这一周，我们练习把“看起来有关”拆成“真的有关”。"),
    ("激励", "人不是按道理行动，是按激励行动。这一周，我们看规则如何悄悄改变人的行为。"),
    ("复利", "小的、持续的东西，最后会赢过大的、一次性的东西。这一周，我们看时间如何放大差异。"),
    ("权力", "权力不只是让人服从，更是让人不需要解释。这一周，我们看权力如何隐藏自己。"),
    ("风险", "看不见的风险最危险。这一周，我们看人如何低估概率、高估控制。"),
    ("概率", "世界是按概率运行的，不是按因果。这一周，我们练习用概率而不是故事去理解事情。"),
    ("合作与背叛", "合作不是善意，是重复博弈的结果。这一周，我们看信任如何被建立，又如何被利用。"),
]

COLUMNS = [
    ("机制", "Mechanism"), ("历史", "History"), ("人物", "Portrait"),
    ("科学", "Science"), ("现场", "Field Notes"), ("共读", "Read Together"), ("复盘", "Review"),
]

START = datetime(2026, 11, 5).date()


def issue_no(date_str):
    p = WDATA / f"{date_str}.json"
    if p.exists():
        try:
            return int(json.loads(p.read_text(encoding="utf-8")).get("issue", 1))
        except Exception:
            pass
    mx = 0
    for f in WDATA.glob("*.json"):
        try:
            mx = max(mx, int(json.loads(f.read_text(encoding="utf-8")).get("issue", 0)))
        except Exception:
            pass
    return mx + 1


def prev_lesson():
    files = sorted(WDATA.glob("*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def prompt(items, d, theme, theme_note, kind, kind_en, prev, short_note=""):
    prev_ctx = ""
    if prev:
        prev_ctx = "上一课的问题：" + str(prev.get("question", "")) + "\n上一课的长期线索：" + "；".join(prev.get("threads", [])[:2])
    return f"""你在主笔《世界课》：一份给父亲和 9 岁男孩的每日通识课。今天是 {d}（{kind}）。
本周主题：{theme}。今日栏目：{kind}。
{short_note}

写今天这一课，只输出 JSON 对象，不要 markdown 代码块，全文中文（专有名词保留英文）。

要求：
1. 篇幅：正文合计不少于 1500 字。column.body 必须 5 段，每段 200—240 字；answer 140—180 字；world 每段 110—140 字；counter 140—180 字。宁可写满，不要写短。
2. 今日一问：一个能打开一扇门的问题，不超过 30 字，不要课本腔。**问题必须和正文讲的是同一件事**，不要问 A 答 B。
3. answer：直接回答，并给一个不显然的机制。
4. column.title：20 字以内的判断句。column.body 五段顺序是 事实 → 机制 → 例子 → 反例或边界 → 推论。column.pull：一句 25—35 字、可以带走的判断。
5. world：用素材里今天的一件真实国际事件，写“世界观察”。title 20 字内；paras 3 段：发生了什么 / 机制是什么 / 被忽略的是什么；miss 80—120 字，必须落在“这对理解世界有什么用”。
6. counter：必须是对本篇最强的反方，不是稻草人。
7. kid.questions：3 个家长可以问孩子的问题，不用术语、不给结论。kid.experiment：40—60 字，5 分钟能做完。
8. reading：3 条，优先用素材里的链接；书或论文可以只写名字，url 留空字符串。不得编造 URL。
9. threads：3 条值得盯几年的长期线索。
10. 语气：安静、好奇、不煽动、不写“你应该”，不做成功学，不做育儿焦虑。事实、推断、猜测三种语气分开。

{prev_ctx}

JSON 结构：
{{"question":"","answer":"","theme_note":"60-80字","column":{{"title":"","body":["","","",""],"pull":""}},"world":{{"title":"","paras":["","",""],"miss":""}},"counter":"","kid":{{"questions":["","",""],"experiment":""}},"reading":[{{"out":"","title":"","note":"","url":""}}],"threads":["","",""]}}

素材（{len(items)} 条）：
{base.corpus(items)}
"""


def cjk_len(obj):
    text = obj.get("answer", "") + "".join(obj.get("column", {}).get("body", []))
    text += "".join(obj.get("world", {}).get("paras", [])) + obj.get("counter", "")
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def validate(obj):
    for k in ("question", "answer", "column", "world", "kid", "counter"):
        if not obj.get(k):
            raise ValueError("缺字段 " + k)
    if len(obj["column"].get("body") or []) < 3:
        raise ValueError("正文段数不足")
    if len(obj["kid"].get("questions") or []) < 3:
        raise ValueError("孩子问题不足")
    return obj


def fallback(items, d, issue, theme, theme_note, kind, kind_en, wd_index):
    top = items[:3]
    return {
        "date": d, "weekday": "星期" + "一二三四五六日"[wd_index], "weekday_index": wd_index,
        "issue": issue, "week": 1, "theme": theme, "theme_note": theme_note, "minutes": 6,
        "question": "今天世界上发生的事，哪一件会在五年后还被提起？",
        "answer": "今天这期没有写成。下面的三条原始报道，是素材里最重要的三件事；明天会补上完整的一课。",
        "column": {"kind": kind, "kind_en": kind_en, "title": "今日三条原始报道",
                   "body": [f"{i['title']}。{i['text'][:120]}" for i in top] or ["暂无素材。"], "pull": ""},
        "world": {"title": "", "paras": [], "miss": ""},
        "counter": "",
        "kid": {"questions": ["今天你听到的最奇怪的一件事是什么？", "它为什么会发生？", "如果是你，会怎么做？"], "experiment": ""},
        "reading": [{"out": i["source"], "title": i["title"], "note": i["text"][:80], "url": i["url"]} for i in top],
        "threads": ["世界的注意力从哪里来，又去了哪里。"],
        "sources": sorted({i["source"] for i in top}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=datetime.now(base.CST).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    WDATA.mkdir(parents=True, exist_ok=True)
    items = base.collect()
    print(f"素材 {len(items)} 条")
    if not items:
        return 1

    d = datetime.strptime(args.date, "%Y-%m-%d").date()
    wd = d.weekday()
    week = (d - START).days // 7 + 1
    theme, theme_note = THEMES[(week - 1) % len(THEMES)]
    kind, kind_en = COLUMNS[wd]
    issue = issue_no(args.date)

    data = None
    short = ""
    if not args.dry_run:
        for attempt in (1, 2):
            try:
                obj = base.call_api(
                    prompt(items, args.date, theme, theme_note, kind, kind_en, prev_lesson(), short), 5000
                )
                cand = validate(obj)
                n = cjk_len(cand)
                if n < 1350 and attempt == 1:
                    short = f"注意：上一版正文只有 {n} 字，太短。本次必须写到 1500 字以上，body 必须 5 段、每段 220—260 字。"
                    print(f"[太短 {n}] 重写", file=sys.stderr)
                    continue
                data = cand
                break
            except Exception as exc:  # noqa: BLE001
                print(f"[世界课失败 {attempt}] {exc}", file=sys.stderr)
    if data:
        base.sanitize_urls(data, {i["url"] for i in items})
    else:
        data = fallback(items, args.date, issue, theme, theme_note, kind, kind_en, wd)

    data.update({
        "date": args.date,
        "weekday": "星期" + "一二三四五六日"[wd],
        "weekday_index": wd,
        "issue": issue,
        "week": week,
        "theme": theme,
        "theme_note": theme_note,
        "minutes": data.get("minutes") or 8,
    })
    data["column"]["kind"] = kind
    data["column"]["kind_en"] = kind_en
    data.setdefault("sources", [])

    out = WDATA / f"{args.date}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 {out}")

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    site_url = os.environ.get("SITE_URL")
    if repo and not site_url:
        owner, name = repo.split("/", 1)
        site_url = (f"https://{owner.lower()}.github.io/" if name.lower() == f"{owner.lower()}.github.io"
                    else f"https://{owner.lower()}.github.io/{name}/")
    publish.build_all(ROOT, site_url)
    print(f"已发布：第{issue:03d}课（{kind}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
