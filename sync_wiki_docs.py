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


def build_downloads() -> str:
    grouped: dict[str, list[Manual]] = {}
    for manual in MANUALS:
        section = Path(manual.output).parts[0]
        grouped.setdefault(section, []).append(manual)

    lines = [
        "# PDF 다운로드",
        "",
        "PDF는 `md/`의 Markdown에서 생성한 읽기 전용 산출물입니다.",
        "내용을 수정할 때는 PDF가 아니라 원본 Markdown을 변경한 뒤 다시 export합니다.",
        "",
        "[사용자 매뉴얼](pdf/user/user-manual.pdf){ .md-button }",
        "",
        "[전체 통합 매뉴얼](pdf/system/server-manage-manual.pdf){ .md-button .md-button--primary }",
        "",
        "## 문서 묶음별 PDF",
        "",
    ]

    section_titles = {
        "backend": "Backend",
        "infra": "Infra",
        "system": "System",
        "user": "User",
    }
    section_descriptions = {
        "backend": "승인, API, 인증, 스케줄러 같은 Admin BE 문서 PDF",
        "infra": "config-server, NodePort, Kerberos, 운영 절차 문서 PDF",
        "system": "GPU 서버 운영 기반과 모듈별 시스템 문서 PDF",
        "user": "학생과 연구원이 보는 사용 절차, 홈페이지 사용법, 백업 안내 PDF",
    }

    for section in ("backend", "infra", "system", "user"):
        manuals = grouped.get(section)
        if not manuals:
            continue
        lines.append(f"### {section_titles.get(section, section)}")
        lines.append("")
        description = section_descriptions.get(section)
        if description:
            lines.append(description)
            lines.append("")
        for manual in manuals:
            lines.append(f"- [{manual.label}](pdf/{manual.output})")
        lines.append("")

    lines.extend(
        [
            "## 다시 생성",
            "",
            "```bash",
            "cd /path/to/admin_wiki",
            "python3 manage.py export",
            "python3 manage.py sync-now",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


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
