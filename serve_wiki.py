#!/usr/bin/env python3
"""Serve the generated static wiki with optional HTTP Basic authentication."""

from __future__ import annotations

import argparse
import base64
import hmac
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_SITE = Path(__file__).resolve().parent / "site"


class WikiHandler(SimpleHTTPRequestHandler):
    server_version = "ServerManageWiki/1.0"

    def __init__(self, *args, directory: str, username: str, password: str, **kwargs) -> None:
        self.wiki_username = username
        self.wiki_password = password
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def authenticated(self) -> bool:
        if not self.wiki_username and not self.wiki_password:
            return True
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Basic "):
            return False
        try:
            supplied = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        expected = f"{self.wiki_username}:{self.wiki_password}"
        return hmac.compare_digest(supplied, expected)

    def require_auth(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Server Manage Wiki", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write("인증이 필요합니다.\n".encode("utf-8"))

    def healthz(self) -> None:
        payload = b"ok\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/healthz":
            self.healthz()
            return
        if not self.authenticated():
            self.require_auth()
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self.path.split("?", 1)[0] == "/healthz":
            self.healthz()
            return
        if not self.authenticated():
            self.require_auth()
            return
        super().do_HEAD()

    def list_directory(self, path: str):
        self.send_error(404, "Directory listing is disabled")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=30097)
    parser.add_argument("--directory", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--no-auth", action="store_true", help="Serve without Basic Auth")
    args = parser.parse_args()

    site = args.directory.resolve()
    if not (site / "index.html").is_file():
        raise SystemExit(f"wiki is not built: {site / 'index.html'}")

    username = "" if args.no_auth else os.environ.get("WIKI_USERNAME", "")
    password = "" if args.no_auth else os.environ.get("WIKI_PASSWORD", "")
    if not args.no_auth and (not username or not password):
        raise SystemExit("set WIKI_USERNAME and WIKI_PASSWORD, or pass --no-auth explicitly")

    handler = partial(WikiHandler, directory=str(site), username=username, password=password)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"serving {site} on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
