"""Builds a structured document from raw PDF elements: metadata from the header
table, sections from heading fonts, and blocks from line gaps and numerals."""
import re
import unicodedata

from app.models.ExtractedDocument import (
    UNVERSIONED,
    Block,
    DocumentMetadata,
    ExtractedDocument,
    Section,
)
from app.models.PageElement import PageElement, TableElement, TextLine

# Layout values measured on the corpus PDFs.
_TITLE_MIN_FONT_SIZE = 14.0
_HEADING_MIN_FONT_SIZE = 10.0
_PARAGRAPH_MIN_GAP = 15.0
_BULLET_PREFIX = "(cid:127)"
_NO_VALUE = "—"

_NUMBERED_HEADING = re.compile(r"^(\d+)\.\s+(.*)$")
_ARTICLE_HEADING = re.compile(r"^Artículo\s+(\d+)\.\s+(.*)$")
_NUMERAL = re.compile(r"^(\d+\.\d+)\s")


class SectionParser:
    def parse(self, source: str, elements: list[PageElement]) -> ExtractedDocument:
        """Split elements at the header table: title above it, sections below it."""
        header_index = self._find_header_table(source, elements)
        metadata = self._parse_metadata(elements[:header_index], elements[header_index])
        sections = self._parse_sections(elements[header_index + 1:])
        return ExtractedDocument(source=source, metadata=metadata, sections=sections)

    def _find_header_table(self, source: str, elements: list[PageElement]) -> int:
        """Return the index of the table whose first cell is "Código"."""
        for index, element in enumerate(elements):
            if isinstance(element, TableElement) and element.rows[0][0] == "Código":
                return index
        raise ValueError(f"header table not found in {source}")

    def _parse_metadata(self, preamble: list[PageElement], header: TableElement) -> DocumentMetadata:
        """Read metadata from the header table, laid out as label/value cell pairs."""
        fields = {
            row[index]: row[index + 1]
            for row in header.rows
            for index in range(0, len(row) - 1, 2)
            if row[index]
        }
        lines = [element for element in preamble if isinstance(element, TextLine)]
        version = fields["Versión"]
        return DocumentMetadata(
            code=fields["Código"],
            version=UNVERSIONED if version == _NO_VALUE else version,
            title=" ".join(line.text for line in lines if line.font_size >= _TITLE_MIN_FONT_SIZE),
            document_type=fields["Tipo"],
            issue_date=fields["Fecha de emisión"],
            issuing_area=fields["Área emisora"],
            issuer=" ".join(line.text for line in lines if line.font_size < _TITLE_MIN_FONT_SIZE),
            replaces=fields.get("Reemplaza a"),
        )

    def _parse_sections(self, elements: list[PageElement]) -> tuple[Section, ...]:
        """Walk the elements in order, opening a new section at each heading."""
        sections: list[Section] = []
        heading_lines: list[str] = []
        blocks: list[Block] = []
        numeral: str | None = None
        previous_line: TextLine | None = None

        def close_section() -> None:
            if heading_lines:
                sections.append(self._build_section(" ".join(heading_lines), blocks))

        for element in elements:
            if isinstance(element, TableElement):
                blocks.append(self._table_block(element, numeral))
                previous_line = None
            elif self._is_heading(element):
                # A heading can wrap onto a second line.
                if blocks or not self._continues_heading(previous_line):
                    close_section()
                    heading_lines, blocks, numeral = [], [], None
                heading_lines.append(element.text)
                previous_line = element
            else:
                numeral = self._append_line(blocks, element, previous_line, numeral)
                previous_line = element

        close_section()
        return tuple(sections)

    def _is_heading(self, line: TextLine) -> bool:
        return line.is_bold and line.font_size >= _HEADING_MIN_FONT_SIZE

    def _continues_heading(self, previous_line: TextLine | None) -> bool:
        return previous_line is not None and self._is_heading(previous_line)

    def _append_line(
        self,
        blocks: list[Block],
        line: TextLine,
        previous_line: TextLine | None,
        numeral: str | None,
    ) -> str | None:
        """Add a line to the blocks and return the numeral now in effect."""
        if line.text.startswith(_BULLET_PREFIX):
            text = line.text.removeprefix(_BULLET_PREFIX).strip()
            blocks.append(Block(kind="list_item", text=text, numeral=numeral))
            return numeral

        match = _NUMERAL.match(line.text)
        if match:
            numeral = match.group(1)
            blocks.append(Block(kind="paragraph", text=line.text, numeral=numeral))
            return numeral

        if self._continues_block(blocks, line, previous_line):
            last = blocks[-1]
            blocks[-1] = Block(kind=last.kind, text=f"{last.text} {line.text}", numeral=last.numeral)
        else:
            blocks.append(Block(kind="paragraph", text=line.text, numeral=numeral))
        return numeral

    def _continues_block(
        self,
        blocks: list[Block],
        line: TextLine,
        previous_line: TextLine | None,
    ) -> bool:
        """A wrapped line sits closer to the previous line than a new paragraph does."""
        if not blocks or previous_line is None or blocks[-1].kind == "table":
            return False
        if self._is_heading(previous_line) or line.page != previous_line.page:
            return False
        return line.top - previous_line.top < _PARAGRAPH_MIN_GAP

    def _table_block(self, table: TableElement, numeral: str | None) -> Block:
        """Keep the table whole and attach it to the numeral it follows, if any."""
        text = " ".join(cell for row in table.rows for cell in row)
        return Block(kind="table", text=text, numeral=numeral, rows=table.rows)

    def _build_section(self, heading: str, blocks: list[Block]) -> Section:
        """Derive the section id: "3" from "3. X", "art-2" from "Artículo 2. X", else a slug."""
        numbered = _NUMBERED_HEADING.match(heading)
        if numbered:
            section_id, title = numbered.groups()
        else:
            article = _ARTICLE_HEADING.match(heading)
            if article:
                section_id, title = f"art-{article.group(1)}", article.group(2)
            else:
                section_id, title = self._slugify(heading), heading
        return Section(section_id=section_id, heading=heading, title=title, blocks=tuple(blocks))

    def _slugify(self, text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text)
        ascii_text = decomposed.encode("ascii", "ignore").decode("ascii").lower()
        return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
