"""Reads the Markdown copy of a document, used only to verify PDF extraction."""
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class MarkdownDocument:
    header: dict[str, str]
    sections: dict[str, str]


class MarkdownRepository:
    def read(self, path: Path) -> MarkdownDocument:
        """Split the file into its YAML header and its body."""
        _, front_matter, body = path.read_text(encoding="utf-8").split("---", 2)
        header = {key: str(value) for key, value in yaml.safe_load(front_matter).items()}
        return MarkdownDocument(header=header, sections=self._read_sections(body))

    def _read_sections(self, body: str) -> dict[str, str]:
        """Map each "## " heading to its plain text; text before the first heading is skipped."""
        sections: dict[str, list[str]] = {}
        current: list[str] | None = None
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                current = sections.setdefault(line[3:], [])
            elif current is not None and line:
                content = self._line_content(line)
                if content:
                    current.append(content)
        return {heading: " ".join(lines) for heading, lines in sections.items()}

    def _line_content(self, line: str) -> str:
        """Strip table and list syntax; a table separator row becomes empty."""
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            return "" if set("".join(cells)) <= {"-"} else " ".join(cells)
        return line[2:] if line.startswith("- ") else line
