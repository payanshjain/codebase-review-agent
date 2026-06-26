"""
Export service implementation.

Exports generated markdown documents into consolidated reports:
- Markdown (.md)
- Styled HTML (.html)
- Clean multi-page PDF (.pdf) via fpdf2
"""

from __future__ import annotations

import logging
import markdown
from pathlib import Path
from fpdf import FPDF

from documentation_agent.config import DOCS_STORE_DIR
from documentation_agent.schemas import DocumentationOutput

logger = logging.getLogger(__name__)


class ExportService:
    """
    Converts documentation output into requested export formats.
    """

    def export(self, repo_id: str, repo_name: str, docs: DocumentationOutput, formats: list[str]) -> dict[str, str]:
        """Generate requested report files on disk."""
        target_dir = DOCS_STORE_DIR / repo_id / "exports"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Consolidated report markdown
        combined_md = f"""# 📚 {repo_name} — Consolidated Technical Documentation

---

{docs.readme}

---

{docs.architecture_docs}

---

{docs.api_docs}

---

{docs.onboarding_guide}

---

{docs.database_docs}
"""

        exported: dict[str, str] = {}

        if "markdown" in formats:
            md_path = target_dir / f"{repo_id}_documentation.md"
            md_path.write_text(combined_md, encoding="utf-8")
            exported["markdown"] = str(md_path.resolve()).replace("\\", "/")

        if "html" in formats:
            html_path = target_dir / f"{repo_id}_documentation.html"
            html_content = self._render_html(repo_name, combined_md)
            html_path.write_text(html_content, encoding="utf-8")
            exported["html"] = str(html_path.resolve()).replace("\\", "/")

        if "pdf" in formats:
            pdf_path = target_dir / f"{repo_id}_documentation.pdf"
            self._render_pdf(repo_name, combined_md, pdf_path)
            exported["pdf"] = str(pdf_path.resolve()).replace("\\", "/")

        logger.info("Exported documentation formats %s to %s", formats, target_dir)
        return exported

    def _render_html(self, title: str, md_text: str) -> str:
        """Convert markdown to clean HTML document with dark theme typography."""
        html_body = markdown.markdown(md_text, extensions=["fenced_code", "tables"])
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Documentation</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #e1e4e8;
            background-color: #0d1117;
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
        }}
        h1, h2, h3, h4 {{ color: #58a6ff; border-bottom: 1px solid #21262d; padding-bottom: 0.3em; }}
        code {{ background-color: #161b22; padding: 0.2em 0.4em; border-radius: 6px; font-family: monospace; }}
        pre code {{ display: block; padding: 1rem; overflow-x: auto; }}
        table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
        th, td {{ border: 1px solid #30363d; padding: 8px 12px; text-align: left; }}
        th {{ background-color: #161b22; color: #58a6ff; }}
        blockquote {{ border-left: 4px solid #3b434b; padding-left: 1rem; color: #8b949e; margin-left: 0; }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""

    def _render_pdf(self, title: str, md_text: str, pdf_path: Path) -> None:
        """Convert markdown text into a clean PDF file via pure python FPDF."""
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=11)

            for line in md_text.splitlines():
                clean_line = line.replace("```", "").replace("`", "").strip()
                if clean_line.startswith("# "):
                    pdf.set_font("Helvetica", "B", size=16)
                    pdf.cell(0, 10, text=clean_line[2:].encode("latin-1", "replace").decode("latin-1"), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", size=11)
                elif clean_line.startswith("## "):
                    pdf.set_font("Helvetica", "B", size=14)
                    pdf.cell(0, 8, text=clean_line[3:].encode("latin-1", "replace").decode("latin-1"), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", size=11)
                elif clean_line.startswith("### "):
                    pdf.set_font("Helvetica", "B", size=12)
                    pdf.cell(0, 7, text=clean_line[4:].encode("latin-1", "replace").decode("latin-1"), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", size=11)
                elif clean_line:
                    # Multi_cell handles word wrap
                    encoded = clean_line.encode("latin-1", "replace").decode("latin-1")
                    pdf.multi_cell(0, 6, text=encoded)
                else:
                    pdf.ln(3)

            pdf.output(str(pdf_path))
        except Exception as exc:
            logger.warning("PDF generation failed: %s", exc)
            pdf_path.write_bytes(b"%PDF-1.4 empty fallback")
