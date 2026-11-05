# -*- coding: utf-8 -*-
"""共享发布：构建《资讯》与《世界课》，并把 站点/ 整体复制到 public/"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build_all(root: Path, site_url: str | None = None):
    env = os.environ.copy()
    if site_url:
        env["SITE_URL"] = site_url
    subprocess.run([sys.executable, str(root / "build.py")], check=True, cwd=str(root), env=env)
    world_build = root / "世界课" / "build_world.py"
    if world_build.exists():
        subprocess.run([sys.executable, str(world_build)], check=True, cwd=str(root), env=env)

    src = root / "站点"
    pub = root / "public"
    if pub.exists():
        shutil.rmtree(pub)
    shutil.copytree(src, pub)
    return pub
