#!/usr/bin/env python3
"""Host-side control entrypoint for the Docker wiki and local PDF export."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = REPO_ROOT / "compose.yml"
EXPORTER = REPO_ROOT / "export_manuals.py"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def compose(*arguments: str) -> None:
    run(["docker", "compose", "--file", str(COMPOSE_FILE), *arguments])


def publish_local() -> None:
    compose("build", "sync")
    compose(
        "run",
        "--rm",
        "--no-deps",
        "--user",
        "0:0",
        "--volume",
        f"{REPO_ROOT}:/source:ro",
        "--entrypoint",
        "/usr/local/bin/wiki-publish-local",
        "sync",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("up", help="Build and start the shared wiki")
    subparsers.add_parser("down", help="Stop containers without deleting volumes")
    subparsers.add_parser("restart", help="Restart both wiki services")
    subparsers.add_parser("status", help="Show container and health status")
    subparsers.add_parser("sync-now", help="Restart the sync loop to fetch main immediately")
    subparsers.add_parser("publish-local", help="Build and publish the current host checkout")
    subparsers.add_parser("export", help="Export PDFs on the host with local Chromium")
    subparsers.add_parser("config", help="Render and validate the Compose configuration")

    logs = subparsers.add_parser("logs", help="Show service logs")
    logs.add_argument("service", nargs="?", choices=("sync", "web"))
    logs.add_argument("--follow", "-f", action="store_true")
    logs.add_argument("--tail", type=int, default=100)

    args = parser.parse_args()
    if args.command == "up":
        publish_local()
        compose("up", "--detach")
    elif args.command == "down":
        compose("down")
    elif args.command == "restart":
        compose("restart")
    elif args.command == "status":
        compose("ps")
    elif args.command == "sync-now":
        compose("restart", "sync")
    elif args.command == "publish-local":
        publish_local()
    elif args.command == "export":
        run([sys.executable, str(EXPORTER)])
    elif args.command == "config":
        compose("config")
    elif args.command == "logs":
        command = ["logs", "--tail", str(args.tail)]
        if args.follow:
            command.append("--follow")
        if args.service:
            command.append(args.service)
        compose(*command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
