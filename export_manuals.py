#!/usr/bin/env python3
"""Export repository MANUAL.md files to individual and combined PDFs.

The renderer intentionally uses only the Python standard library. It supports
the Markdown constructs used by the manuals and delegates pagination/PDF
generation to a locally installed Chromium-family browser.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = REPO_ROOT / "wiki"
MD_DIR = WIKI_DIR / "md"
DEFAULT_OUTPUT = WIKI_DIR / "pdf"


@dataclass(frozen=True)
class Manual:
    slug: str
    label: str
    source: Path
    output: str


MANUALS = (
    Manual(
        "server-manage",
        "전체 구조",
        MD_DIR / "system" / "index.md",
        "system/server-manage-index.pdf",
    ),
    Manual(
        "container-images",
        "container-images",
        MD_DIR / "system" / "container-images.md",
        "system/container-images-manual.pdf",
    ),
    Manual(
        "kerberos-nfs",
        "kerberos-nfs",
        MD_DIR / "system" / "kerberos-nfs.md",
        "system/kerberos-nfs-manual.pdf",
    ),
    Manual(
        "monitoring",
        "monitoring",
        MD_DIR / "system" / "monitoring.md",
        "system/monitoring-manual.pdf",
    ),
    Manual(
        "remote-operations",
        "remote-operations",
        MD_DIR / "system" / "remote-operations.md",
        "system/remote-operations-manual.pdf",
    ),
    Manual(
        "server-state",
        "server-state",
        MD_DIR / "system" / "server-state.md",
        "system/server-state-manual.pdf",
    ),
    Manual(
        "user-lifecycle",
        "user-lifecycle",
        MD_DIR / "system" / "user-lifecycle.md",
        "system/user-lifecycle-manual.pdf",
    ),
)


STYLE = r"""
@page {
  size: A4;
  margin: 17mm 16mm 18mm 16mm;
}
* { box-sizing: border-box; }
html {
  font-family: "Noto Sans CJK KR", "Noto Sans KR", "Malgun Gothic", sans-serif;
  color: #18212b;
  font-size: 10.3pt;
  line-height: 1.62;
}
body { margin: 0; padding: 0; }
h1, h2, h3, h4 {
  display: block;
  width: 100%;
  color: #12263a;
  line-height: 1.28;
  page-break-after: avoid;
  break-after: avoid-page;
}
h1 {
  margin: 0 0 10mm;
  padding-bottom: 4mm;
  border-bottom: 2px solid #235789;
  font-size: 23pt;
  letter-spacing: -0.035em;
}
h2 {
  margin: 9mm 0 3mm;
  padding-bottom: 1.5mm;
  border-bottom: 1px solid #bdd1e4;
  font-size: 16pt;
}
h3 { clear: both; margin: 6mm 0 2mm; font-size: 12.5pt; }
h3::after { content: ""; display: block; height: 1mm; }
h4 { margin: 4mm 0 1.5mm; font-size: 11pt; }
p { margin: 0 0 3.2mm; orphans: 3; widows: 3; }
a { color: #1b5e92; text-decoration: none; }
strong { color: #102f4d; }
blockquote {
  margin: 0 0 5mm;
  padding: 3mm 4mm;
  border-left: 3px solid #3b82a8;
  background: #eef5f8;
  color: #324b5f;
}
blockquote p { margin: 0; }
code {
  font-family: "Noto Sans Mono CJK KR", "D2Coding", monospace;
  font-size: 0.9em;
  color: #8c2f39;
  background: #f3f5f7;
  padding: 0.05em 0.25em;
  border-radius: 2px;
}
pre {
  margin: 2.5mm 0 4.5mm;
  padding: 3.5mm 4mm;
  border: 1px solid #d7e0e8;
  border-radius: 4px;
  background: #f7f9fb;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  page-break-inside: avoid;
}
pre code {
  color: #172b3a;
  background: transparent;
  padding: 0;
  font-size: 8.6pt;
}
ul, ol { margin: 1.5mm 0 4mm; padding-left: 6.5mm; }
li { margin: 0 0 1.2mm; }
table {
  width: 100%;
  margin: 2.5mm 0 5mm;
  border-collapse: collapse;
  font-size: 8.7pt;
  page-break-inside: auto;
}
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
th, td {
  padding: 2mm 2.2mm;
  border: 1px solid #b9c8d4;
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}
th { background: #dfeaf2; color: #15354f; }
tbody tr:nth-child(even) { background: #f8fafb; }
hr { border: 0; border-top: 1px solid #b9c8d4; margin: 8mm 0; }
.manual-section { break-before: page; page-break-before: always; }
.manual-section.first { break-before: auto; page-break-before: auto; }
.cover {
  height: 250mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  break-after: page;
  page-break-after: always;
}
.cover h1 { font-size: 30pt; border: 0; margin-bottom: 4mm; }
.cover .subtitle { font-size: 14pt; color: #48647a; margin-bottom: 16mm; }
.cover .meta { color: #5c7080; }
.toc {
  break-after: page;
  page-break-after: always;
}
.toc ol { font-size: 12pt; line-height: 1.8; }
.source-note {
  margin: -6mm 0 8mm;
  color: #647786;
  font-size: 8.5pt;
}
"""


TABLE_DELIMITER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
UL_ITEM = re.compile(r"^\s*[-*+]\s+(.*)$")
OL_ITEM = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def render_inline(value: str) -> str:
    """Render the small inline Markdown subset used by the manuals."""
    code_tokens: list[str] = []

    def hold_code(match: re.Match[str]) -> str:
        code_tokens.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00CODE{len(code_tokens) - 1}\x00"

    value = re.sub(r"`([^`]+)`", hold_code, value)
    value = html.escape(value, quote=False)
    value = re.sub(
        r"\[([^]]+)]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        value,
    )
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)
    for index, token in enumerate(code_tokens):
        value = value.replace(f"\x00CODE{index}\x00", token)
    return value


def split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_special(lines: list[str], index: int) -> bool:
    line = lines[index]
    if not line.strip():
        return True
    if line.startswith("```") or HEADING.match(line):
        return True
    if UL_ITEM.match(line) or OL_ITEM.match(line) or line.startswith(">"):
        return True
    if re.match(r"^\s*(?:---+|___+|\*\*\*+)\s*$", line):
        return True
    if index + 1 < len(lines) and "|" in line and TABLE_DELIMITER.match(lines[index + 1]):
        return True
    return False


def markdown_to_html(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if line.startswith("```"):
            language = line[3:].strip()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            class_name = f' class="language-{html.escape(language, quote=True)}"' if language else ""
            out.append(f"<pre><code{class_name}>{html.escape(chr(10).join(code))}</code></pre>")
            continue

        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            anchor = re.sub(r"[^a-z0-9가-힣]+", "-", title.lower()).strip("-")
            out.append(f'<h{level} id="{html.escape(anchor, quote=True)}">{render_inline(title)}</h{level}>')
            index += 1
            continue

        if index + 1 < len(lines) and "|" in line and TABLE_DELIMITER.match(lines[index + 1]):
            headers = split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                rows.append(split_table_row(lines[index]))
                index += 1
            out.append("<table><thead><tr>")
            out.extend(f"<th>{render_inline(cell)}</th>" for cell in headers)
            out.append("</tr></thead><tbody>")
            for row in rows:
                padded = row + [""] * max(0, len(headers) - len(row))
                out.append("<tr>")
                out.extend(f"<td>{render_inline(cell)}</td>" for cell in padded[: len(headers)])
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        unordered = UL_ITEM.match(line)
        if unordered:
            items: list[str] = []
            while index < len(lines):
                match = UL_ITEM.match(lines[index])
                if not match:
                    break
                item_lines = [match.group(1)]
                index += 1
                while index < len(lines) and lines[index].strip():
                    if UL_ITEM.match(lines[index]) or OL_ITEM.match(lines[index]):
                        break
                    if (
                        lines[index].startswith("```")
                        or HEADING.match(lines[index])
                        or lines[index].startswith(">")
                    ):
                        break
                    item_lines.append(lines[index].strip())
                    index += 1
                items.append(" ".join(item_lines))
            out.append("<ul>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ul>")
            continue

        ordered = OL_ITEM.match(line)
        if ordered:
            items = []
            while index < len(lines):
                match = OL_ITEM.match(lines[index])
                if not match:
                    break
                item_lines = [match.group(1)]
                index += 1
                while index < len(lines) and lines[index].strip():
                    if OL_ITEM.match(lines[index]) or UL_ITEM.match(lines[index]):
                        break
                    if (
                        lines[index].startswith("```")
                        or HEADING.match(lines[index])
                        or lines[index].startswith(">")
                    ):
                        break
                    item_lines.append(lines[index].strip())
                    index += 1
                items.append(" ".join(item_lines))
            out.append("<ol>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ol>")
            continue

        if line.startswith(">"):
            quoted: list[str] = []
            while index < len(lines) and lines[index].startswith(">"):
                quoted.append(lines[index][1:].lstrip())
                index += 1
            out.append(f"<blockquote><p>{render_inline(' '.join(quoted))}</p></blockquote>")
            continue

        if re.match(r"^\s*(?:---+|___+|\*\*\*+)\s*$", line):
            out.append("<hr>")
            index += 1
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines) and not is_special(lines, index):
            paragraph.append(lines[index].strip())
            index += 1
        out.append(f"<p>{render_inline(' '.join(paragraph))}</p>")

    return "\n".join(out)


def html_document(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>{body}</body>
</html>
"""


def find_browser(explicit: str | None) -> str:
    if explicit:
        resolved = shutil.which(explicit) or (explicit if Path(explicit).exists() else None)
        if resolved:
            return str(resolved)
        raise FileNotFoundError(f"browser not found: {explicit}")
    for candidate in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError("install google-chrome, chromium, or chromium-browser")


def print_pdf(browser: str, html_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        browser,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--allow-file-access-from-files",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={output_path}",
        html_path.resolve().as_uri(),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True, timeout=120)
    if completed.returncode != 0 or not output_path.exists():
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"PDF export failed for {output_path.name}: {detail}")
    output_path.chmod(0o644)


def validate_sources() -> None:
    missing = [str(manual.source) for manual in MANUALS if not manual.source.is_file()]
    if missing:
        raise FileNotFoundError("missing manual source(s): " + ", ".join(missing))


def combined_body(rendered: list[tuple[Manual, str]]) -> str:
    cover = f"""
<section class="cover">
  <h1>Server Manage 운영 위키</h1>
  <p class="subtitle">DECS 서버 관리 코드의 기능, 경계와 설계 의도</p>
  <p class="meta">문서 기준: 2026-07-17 저장소 상태</p>
  <p class="meta">소스: {html.escape(str(REPO_ROOT))}</p>
</section>
"""
    toc = ["<section class=\"toc\"><h1>목차</h1><ol>"]
    toc.extend(f'<li><a href="#{manual.slug}">{html.escape(manual.label)}</a></li>' for manual, _ in rendered)
    toc.append("</ol></section>")
    sections: list[str] = []
    for manual, content in rendered:
        source = manual.source.relative_to(REPO_ROOT)
        source_note = f'<p class="source-note">원본: {html.escape(str(source))}</p>'
        annotated_content = content.replace("</h1>", f"</h1>{source_note}", 1)
        sections.append(
            f'<section class="manual-section" id="{manual.slug}">'
            f'{annotated_content}</section>'
        )
    return cover + "".join(toc) + "".join(sections)


def export(browser: str, output_dir: Path, keep_html: bool) -> list[Path]:
    validate_sources()
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = [(manual, markdown_to_html(manual.source.read_text(encoding="utf-8"))) for manual in MANUALS]
    outputs: list[Path] = []

    with tempfile.TemporaryDirectory(prefix="server-manual-") as temp_name:
        temp_dir = Path(temp_name)
        for manual, body in rendered:
            document = html_document(manual.label, body)
            html_path = temp_dir / f"{manual.slug}.html"
            html_path.write_text(document, encoding="utf-8")
            if keep_html:
                html_output = output_dir / "system" / f"{manual.slug}.html"
                html_output.parent.mkdir(parents=True, exist_ok=True)
                html_output.write_text(document, encoding="utf-8")
            output_path = output_dir / manual.output
            output_path.parent.mkdir(parents=True, exist_ok=True)
            print_pdf(browser, html_path, output_path)
            outputs.append(output_path)

        combined = html_document("Server Manage 운영 위키", combined_body(rendered))
        combined_html = temp_dir / "server-manage-manual.html"
        combined_html.write_text(combined, encoding="utf-8")
        if keep_html:
            combined_html_output = output_dir / "system" / combined_html.name
            combined_html_output.parent.mkdir(parents=True, exist_ok=True)
            combined_html_output.write_text(combined, encoding="utf-8")
        combined_pdf = output_dir / "system" / "server-manage-manual.pdf"
        print_pdf(browser, combined_html, combined_pdf)
        outputs.append(combined_pdf)

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Chrome/Chromium executable or path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--keep-html", action="store_true", help="Keep intermediate HTML beside PDFs")
    args = parser.parse_args()

    browser = find_browser(args.browser)
    outputs = export(browser, args.output_dir.resolve(), args.keep_html)
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
