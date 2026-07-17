#!/usr/bin/env python3
"""Sync repository MANUAL.md sources into the generated MkDocs docs tree."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from export_manuals import MANUALS, REPO_ROOT


WIKI_DIR = REPO_ROOT / "wiki"
DEFAULT_OUTPUT = WIKI_DIR / "wiki-docs"
PDF_DIR = WIKI_DIR / "pdf"
ASSET_DIR = WIKI_DIR / "wiki-assets"


def rewrite_links(markdown: str) -> str:
    replacements = {
        "container-images/MANUAL.md": "container-images.md",
        "kerberos-nfs/MANUAL.md": "kerberos-nfs.md",
        "monitoring/MANUAL.md": "monitoring.md",
        "remote-operations/MANUAL.md": "remote-operations.md",
        "server-state/MANUAL.md": "server-state.md",
        "user-lifecycle/MANUAL.md": "user-lifecycle.md",
        "wiki/README.md": "downloads.md",
    }
    for source, target in replacements.items():
        markdown = markdown.replace(f"]({source})", f"]({target})")
    return markdown


def page_name(slug: str) -> str:
    return "index.md" if slug == "server-manage" else f"{slug}.md"


def build_downloads() -> str:
    lines = [
        "# PDF 다운로드",
        "",
        "PDF는 각 디렉터리의 `MANUAL.md`에서 생성한 읽기 전용 산출물입니다.",
        "내용을 수정할 때는 PDF가 아니라 원본 Markdown을 변경한 뒤 다시 export합니다.",
        "",
        "[전체 통합 매뉴얼](pdf/server-manage-manual.pdf){ .md-button .md-button--primary }",
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
            "python3 wiki/export_manuals.py",
            "python3 wiki/sync_wiki_docs.py",
            "wiki/.venv/bin/mkdocs build --clean -f wiki/mkdocs.yml",
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
        source = rewrite_links(manual.source.read_text(encoding="utf-8"))
        if manual.slug != "server-manage":
            pdf_button = f"\n[이 문서의 PDF 열기](pdf/{manual.output}){{ .md-button }}\n\n"
            first_break = source.find("\n")
            if first_break >= 0:
                source = source[: first_break + 1] + pdf_button + source[first_break + 1 :]
        (output_dir / page_name(manual.slug)).write_text(source, encoding="utf-8")

    (output_dir / "downloads.md").write_text(build_downloads(), encoding="utf-8")

    stylesheet_target = output_dir / "stylesheets"
    stylesheet_target.mkdir(mode=0o755)
    shutil.copy2(ASSET_DIR / "extra.css", stylesheet_target / "extra.css")

    pdf_target = output_dir / "pdf"
    pdf_target.mkdir(mode=0o755)
    if PDF_DIR.is_dir():
        for pdf in sorted(PDF_DIR.glob("*.pdf")):
            shutil.copy2(pdf, pdf_target / pdf.name)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(sync(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
