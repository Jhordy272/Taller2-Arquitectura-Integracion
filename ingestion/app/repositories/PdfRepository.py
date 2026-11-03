"""Reads the text lines and tables of a PDF, in reading order."""
from pathlib import Path

import pdfplumber

from app.models.PageElement import PageElement, TableElement, TextLine

# The footer disclaimer uses the smallest font in the corpus PDFs.
_FOOTER_MAX_FONT_SIZE = 7.0


class PdfRepository:
    def read(self, path: Path) -> list[PageElement]:
        """Return the elements of every page, in order."""
        elements: list[PageElement] = []
        with pdfplumber.open(path) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                elements.extend(self._read_page(page, number))
        return elements

    def _read_page(self, page, number: int) -> list[PageElement]:
        """Merge tables and free text by vertical position, skipping footers."""
        tables = page.find_tables()
        elements: list[PageElement] = [
            TableElement(page=number, top=table.bbox[1], rows=self._clean_rows(table.extract()))
            for table in tables
        ]
        for line in page.extract_text_lines():
            first_char = line["chars"][0]
            if first_char["size"] <= _FOOTER_MAX_FONT_SIZE:
                continue
            if self._is_inside_table(line, tables):
                continue
            elements.append(
                TextLine(
                    page=number,
                    top=line["top"],
                    text=line["text"].strip(),
                    is_bold="Bold" in first_char["fontname"],
                    font_size=first_char["size"],
                )
            )
        return sorted(elements, key=lambda element: element.top)

    def _is_inside_table(self, line: dict, tables: list) -> bool:
        """Table text comes from the table itself, so its lines are skipped."""
        middle = (line["top"] + line["bottom"]) / 2
        return any(table.bbox[1] <= middle <= table.bbox[3] for table in tables)

    def _clean_rows(self, rows: list[list[str | None]]) -> tuple[tuple[str, ...], ...]:
        """Join cell text wrapped onto several lines."""
        return tuple(
            tuple(" ".join((cell or "").split()) for cell in row)
            for row in rows
        )
