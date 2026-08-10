#!/usr/bin/env python3
"""Sync categorized wiki Markdown and PDFs into the generated MkDocs tree."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from export_manuals import MANUALS, REPO_ROOT, Manual


DEFAULT_OUTPUT = REPO_ROOT / "wiki-docs"
PDF_DIR = REPO_ROOT / "pdf"
MD_DIR = REPO_ROOT / "md"
ASSET_DIR = REPO_ROOT / "assets"


def rewrite_links(markdown: str, slug: str) -> str:
    if slug != "server-manage":
        return markdown
    return markdown.replace("](../../pdf/system/", "](../pdf/system/")


def page_name(manual: Manual) -> Path:
    return manual.source.relative_to(MD_DIR)


def sync(output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.parent != REPO_ROOT.resolve():
        raise ValueError(f"output directory must be directly under {REPO_ROOT.resolve()}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, mode=0o755)

    for manual in MANUALS:
        source = rewrite_links(manual.source.read_text(encoding="utf-8"), manual.slug)
        page_relative = page_name(manual)
        page_target = output_dir / page_relative
        page_target.parent.mkdir(parents=True, exist_ok=True)
        page_target.write_text(source, encoding="utf-8")

    known_sources = {manual.source.resolve() for manual in MANUALS}
    for source_md in sorted(MD_DIR.rglob("*.md")):
        if source_md.resolve() in known_sources:
            continue
        relative = source_md.relative_to(MD_DIR)
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_md, target)

    # md 옆의 이미지(.png)도 함께 복사 — 문서의 상대 경로 참조가 빌드 트리에서도 유효하도록
    for asset in sorted(MD_DIR.rglob("*.png")):
        relative = asset.relative_to(MD_DIR)
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, target)

    stylesheet_target = output_dir / "stylesheets"
    stylesheet_target.mkdir(mode=0o755)
    shutil.copy2(ASSET_DIR / "extra.css", stylesheet_target / "extra.css")

    pdf_target = output_dir / "pdf"
    pdf_target.mkdir(mode=0o755)
    if PDF_DIR.is_dir():
        artifacts = [
            path
            for path in PDF_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in {".pdf", ".zip"}
        ]
        for artifact in sorted(artifacts):
            relative = artifact.relative_to(PDF_DIR)
            target = pdf_target / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact, target)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(sync(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
