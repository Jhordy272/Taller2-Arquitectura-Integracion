"""Domain entities: raw elements read from a PDF page, in reading order."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TextLine:
    page: int
    top: float
    text: str
    is_bold: bool
    font_size: float


@dataclass(frozen=True)
class TableElement:
    page: int
    top: float
    rows: tuple[tuple[str, ...], ...]


PageElement = TextLine | TableElement
