#!/usr/bin/env python3
"""Self-hosted remote-support portal for RustDesk.

The customer opens the web page and clicks "실행파일 접속". The portal serves the
stock RustDesk Windows executable under a file name that RustDesk itself parses
on first start (see src/custom_server.rs and is_quick_support_exe in
src/core_main.rs):

    rustdesk-qs--<reversed base64url(JSON)>.exe

* "-qs-" makes it start as a Quick Support client (no installation needed).
* The encoded JSON points it at this site's own hbbs/hbbr server and key.

Only the Python standard library is used.
"""

import base64
import html
import json
import os
import re
import shutil
import sys
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT, "static")
FILES_DIR = os.environ.get("FILES_DIR", os.path.join(ROOT, "files"))
EXE_PATH = os.path.join(FILES_DIR, "rustdesk.exe")


def env(name, default=""):
    return os.environ.get(name, default).strip()


def read_public_key():
    key = env("RUSTDESK_KEY")
    if key:
        return key
    path = env("RUSTDESK_KEY_FILE", "/rustdesk-data/id_ed25519.pub")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def server_config():
    host = env("RUSTDESK_HOST")
    cfg = {"host": host, "key": read_public_key()}
    relay = env("RUSTDESK_RELAY", f"{host}:21117" if host else "")
    if relay:
        cfg["relay"] = relay
    api = env("RUSTDESK_API")
    if api:
        cfg["api"] = api
    return cfg


def encode_config(cfg):
    """Encode cfg the way custom_server::get_custom_server_from_string decodes it.

    RustDesk splits the file name on "--" and "(", so the token must contain
    neither and must not start with "-". Trailing JSON whitespace is harmless,
    so pad until the encoding is clean.
    """
    body = json.dumps(cfg, separators=(",", ":"))
    for pad in range(64):
        raw = (body + " " * pad).encode("utf-8")
        token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")[::-1]
        if "--" not in token and not token.startswith("-") and not token.endswith("-"):
            return token
    raise ValueError("could not encode config")


def decode_config(file_name):
    """Python port of the RustDesk parser, used by the tests."""
    s = file_name
    if s.lower().endswith(".exe"):
        s = s[:-4]
    for part in s.split("--"):
        for piece in [part] + part.split("("):
            piece = piece.strip()[::-1]
            try:
                data = base64.urlsafe_b64decode(piece + "=" * (-len(piece) % 4))
                cfg = json.loads(data)
            except ValueError:
                continue
            if isinstance(cfg, dict) and cfg.get("host"):
                return cfg
    return None


def download_name(cfg):
    prefix = re.sub(r"[^A-Za-z0-9_]", "", env("EXE_PREFIX", "rustdesk")) or "rustdesk"
    return f"{prefix}-qs--{encode_config(cfg)}.exe"


def ensure_exe():
    if os.path.isfile(EXE_PATH):
        return
    url = env("RUSTDESK_EXE_URL")
    if not url:
        print(f"[portal] {EXE_PATH} is missing and RUSTDESK_EXE_URL is empty", file=sys.stderr)
        return
    os.makedirs(FILES_DIR, exist_ok=True)
    tmp = EXE_PATH + ".part"
    print(f"[portal] downloading {url}", file=sys.stderr)
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, EXE_PATH)
    except OSError as e:
        print(f"[portal] download failed: {e}", file=sys.stderr)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self.send_index()
        if path == "/download":
            return self.send_exe()
        if path == "/healthz":
            return self.send_text("ok")
        return super().do_GET()

    def send_text(self, text, status=HTTPStatus.OK, ctype="text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_index(self):
        with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
            page = f.read()
        values = {
            "COMPANY": env("COMPANY_NAME", "고객지원센터"),
            "PHONE": env("SUPPORT_PHONE", ""),
            "HOURS": env("SUPPORT_HOURS", "평일 09:00 ~ 18:00"),
        }
        for k, v in values.items():
            page = page.replace("{{" + k + "}}", html.escape(v))
        self.send_text(page, ctype="text/html; charset=utf-8")

    def send_exe(self):
        cfg = server_config()
        if not cfg["host"] or not cfg["key"]:
            return self.send_text("서버 설정(RUSTDESK_HOST / 공개키)이 아직 준비되지 않았습니다.",
                                  HTTPStatus.SERVICE_UNAVAILABLE)
        if not os.path.isfile(EXE_PATH):
            return self.send_text("실행파일이 아직 준비되지 않았습니다. 관리자에게 문의하세요.",
                                  HTTPStatus.SERVICE_UNAVAILABLE)
        name = download_name(cfg)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(EXE_PATH)))
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(EXE_PATH, "rb") as f:
            shutil.copyfileobj(f, self.wfile)


def main():
    ensure_exe()
    port = int(env("PORT", "8080"))
    print(f"[portal] listening on :{port}", file=sys.stderr)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
