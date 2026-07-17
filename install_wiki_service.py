#!/usr/bin/env python3
"""Install MkDocs dependencies and start the user systemd wiki service."""

from __future__ import annotations

import argparse
import os
import subprocess
import venv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = REPO_ROOT / "wiki"
UNIT_TEMPLATE = WIKI_DIR / "systemd" / "server-manage-wiki.service.in"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
UNIT_FILE = UNIT_DIR / "server-manage-wiki.service"
VENV_DIR = WIKI_DIR / ".venv"
REQUIREMENTS_FILE = WIKI_DIR / "wiki-requirements.txt"


def install_unit() -> None:
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    template = UNIT_TEMPLATE.read_text(encoding="utf-8")
    rendered = template.replace("@REPO_ROOT@", str(REPO_ROOT))
    UNIT_FILE.write_text(rendered, encoding="utf-8")
    UNIT_FILE.chmod(0o644)


def ensure_dependencies() -> None:
    python = VENV_DIR / "bin" / "python"
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS_FILE)],
        check=True,
    )


def systemctl(*args: str) -> None:
    subprocess.run(["systemctl", "--user", *args], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-start", action="store_true")
    args = parser.parse_args()

    if os.geteuid() == 0:
        raise SystemExit("run this installer as the account that will own the user service; do not use sudo")

    for source in (
        UNIT_TEMPLATE,
        WIKI_DIR / "mkdocs.yml",
        REQUIREMENTS_FILE,
        WIKI_DIR / "sync_wiki_docs.py",
        WIKI_DIR / "serve_wiki.py",
    ):
        if not source.is_file():
            raise SystemExit(f"missing required file: {source}")

    ensure_dependencies()
    install_unit()
    systemctl("daemon-reload")
    if not args.no_start:
        systemctl("enable", "--now", UNIT_FILE.name)

    print(f"installed: {UNIT_FILE}")
    if not args.no_start:
        print("service: server-manage-wiki.service")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
