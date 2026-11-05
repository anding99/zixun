# -*- coding: utf-8 -*-
"""
一键把《资讯》部署到 GitHub Pages（不需要 git）
前置：pip install pynacl

用法：
  set GITHUB_TOKEN=ghp_xxx
  python 云版/deploy_github.py --repo zixun --key sk-xxx
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {"工具", "_test", "public", "__pycache__", ".git"}
SKIP_SUFFIX = {".png", ".exe", ".zip", ".log"}
SKIP_FILES = {"公网链接.txt"}


def api(method, path, token, data=None):
    url = API + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "zixun-deploy",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"message": raw}
        return e.code, payload


def collect_files():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        parts = set(rel.parts)
        if parts & SKIP_DIRS:
            continue
        if p.suffix.lower() in SKIP_SUFFIX or p.name in SKIP_FILES:
            continue
        if p.name.endswith((".cmd", ".ps1", ".url")):
            continue
        out.append((rel.as_posix(), p))
    out.sort()
    return out


def put_file(token, owner, repo, branch, rel, path):
    content = base64.b64encode(path.read_bytes()).decode()
    info = {"message": f"add {rel}", "content": content, "branch": branch}
    status, existing = api("GET", f"/repos/{owner}/{repo}/contents/{urllib.parse.quote(rel)}?ref={branch}", token)
    if status == 200 and isinstance(existing, dict) and existing.get("sha"):
        info["sha"] = existing["sha"]
        info["message"] = f"update {rel}"
    code, payload = api("PUT", f"/repos/{owner}/{repo}/contents/{urllib.parse.quote(rel)}", token, info)
    if code not in (200, 201):
        raise RuntimeError(f"上传 {rel} 失败: {code} {payload.get('message')}")


def set_secret(token, owner, repo, name, value):
    from nacl import encoding, public
    code, key = api("GET", f"/repos/{owner}/{repo}/actions/secrets/public-key", token)
    if code != 200:
        raise RuntimeError(f"取公钥失败: {code} {key}")
    pk = public.PublicKey(key["key"].encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(value.encode())
    encrypted = base64.b64encode(sealed).decode()
    code, payload = api("PUT", f"/repos/{owner}/{repo}/actions/secrets/{name}", token, {
        "encrypted_value": encrypted, "key_id": key["key_id"],
    })
    if code not in (201, 204):
        raise RuntimeError(f"设置 secret 失败: {code} {payload}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="zixun")
    ap.add_argument("--key", required=True, help="DeepSeek API key")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("缺少 GITHUB_TOKEN 环境变量", file=sys.stderr)
        return 1

    code, me = api("GET", "/user", token)
    if code != 200:
        print(f"Token 无效: {code} {me.get('message')}", file=sys.stderr)
        return 1
    owner = me["login"]
    print(f"账号：{owner}")

    code, repo = api("POST", "/user/repos", token, {
        "name": args.repo,
        "private": bool(args.private),
        "auto_init": True,
        "description": "个人每日资讯台：全球视野 + 深度分析",
        "has_issues": False,
        "has_wiki": False,
    })
    if code == 422:
        code, repo = api("GET", f"/repos/{owner}/{args.repo}", token)
    if code not in (200, 201):
        print(f"建仓失败: {code} {repo.get('message')}", file=sys.stderr)
        return 1
    branch = repo.get("default_branch", "main")
    print(f"仓库：{owner}/{args.repo}（{branch}）")

    files = collect_files()
    print(f"待上传 {len(files)} 个文件")
    for i, (rel, path) in enumerate(files, 1):
        put_file(token, owner, args.repo, branch, rel, path)
        if i % 5 == 0 or i == len(files):
            print(f"  {i}/{len(files)}")

    print("写入 DEEPSEEK_API_KEY …")
    set_secret(token, owner, args.repo, "DEEPSEEK_API_KEY", args.key.strip())

    code, pages = api("POST", f"/repos/{owner}/{args.repo}/pages", token, {"build_type": "workflow"})
    if code not in (201, 204):
        api("PUT", f"/repos/{owner}/{args.repo}/pages", token, {"build_type": "workflow"})
    print("Pages 已开启（GitHub Actions 源）")

    time.sleep(3)
    code, run = api("POST", f"/repos/{owner}/{args.repo}/actions/workflows/daily.yml/dispatches", token, {"ref": branch})
    if code not in (204, 200):
        print(f"触发工作流失败: {code} {run}", file=sys.stderr)
    else:
        print("已触发第一次运行")

    url = f"https://{owner.lower()}.github.io/{args.repo}/"
    print(json.dumps({
        "owner": owner,
        "repo": args.repo,
        "branch": branch,
        "pages": url,
        "actions": f"https://github.com/{owner}/{args.repo}/actions",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
