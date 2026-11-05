#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资讯 · 本地服务：把 站点/ 目录发布到 http://127.0.0.1:8790/"""
import argparse
import http.server
import socket
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "站点"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):  # 安静一点，只记错误
        if str(args[1] if len(args) > 1 else "") not in ("200", "304"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("223.5.5.5", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    if not (ROOT / "index.html").exists():
        print("站点还没有生成，先运行：python build.py")
        return 1

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((args.host, args.port), Handler) as httpd:
        print(f"资讯台已启动：http://127.0.0.1:{args.port}/")
        if args.host == "0.0.0.0":
            ip = lan_ip()
            if ip:
                print(f"同一局域网可访问：http://{ip}:{args.port}/")
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
