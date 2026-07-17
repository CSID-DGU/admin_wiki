#!/usr/bin/env python3
"""Sync categorized wiki Markdown and PDFs into the generated MkDocs tree."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from export_manuals import MANUALS, REPO_ROOT


WIKI_DIR = REPO_ROOT / "wiki"
DEFAULT_OUTPUT = WIKI_DIR / "wiki-docs"
PDF_DIR = WIKI_DIR / "pdf"
MD_DIR = WIKI_DIR / "md"
ASSET_DIR = WIKI_DIR / "wiki-assets"


def rewrite_links(markdown: str, slug: str) -> str:
    if slug != "server-manage":
        return markdown
    return markdown.replace("](../../pdf/system/", "](../pdf/system/")


def page_name(slug: str) -> str:
    return f"system/{'index' if slug == 'server-manage' else slug}.md"


def build_downloads() -> str:
    lines = [
        "# PDF 다운로드",
        "",
        "PDF는 `wiki/md/`의 Markdown에서 생성한 읽기 전용 산출물입니다.",
        "내용을 수정할 때는 PDF가 아니라 원본 Markdown을 변경한 뒤 다시 export합니다.",
        "",
        "[전체 통합 매뉴얼](pdf/system/server-manage-manual.pdf){ .md-button .md-button--primary }",
        "",
        "## 모듈별 PDF",
        "",
    ]
    for manual in MANUALS:
        lines.append(f"- [{manual.label}](pdf/{manual.output})")
    lines.extend(
        [
            "",
            "## 다시 생성",
            "",
            "```bash",
            "cd /path/to/admin_infra_server",
            "python3 wiki/manage.py export",
            "python3 wiki/manage.py sync-now",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def sync(output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.parent != WIKI_DIR.resolve():
        raise ValueError(f"output directory must be directly under {WIKI_DIR.resolve()}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, mode=0o755)

    for manual in MANUALS:
        source = rewrite_links(manual.source.read_text(encoding="utf-8"), manual.slug)
        if manual.slug != "server-manage":
            pdf_button = f"\n[이 문서의 PDF 열기](../pdf/{manual.output}){{ .md-button }}\n\n"
            first_break = source.find("\n")
            if first_break >= 0:
                source = source[: first_break + 1] + pdf_button + source[first_break + 1 :]
        page_target = output_dir / page_name(manual.slug)
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

    (output_dir / "downloads.md").write_text(build_downloads(), encoding="utf-8")

    stylesheet_target = output_dir / "stylesheets"
    stylesheet_target.mkdir(mode=0o755)
    shutil.copy2(ASSET_DIR / "extra.css", stylesheet_target / "extra.css")

    pdf_target = output_dir / "pdf"
    pdf_target.mkdir(mode=0o755)
    if PDF_DIR.is_dir():
        for pdf in sorted(PDF_DIR.rglob("*.pdf")):
            relative = pdf.relative_to(PDF_DIR)
            target = pdf_target / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, target)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(sync(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
