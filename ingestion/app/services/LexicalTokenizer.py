"""Tokenizer of the lexical branch (ADR-05). Normalizes accents and case, and keeps
identifiers and numbers whole so "RES-CREG-0043-2024" or "1.100" stay searchable."""
import re
import unicodedata
import zlib

TOKENIZER_VERSION = "1"

# BM25 parameters; the IDF factor is applied by Qdrant at query time.
_K1 = 1.2
_B = 0.75

_TOKEN = re.compile(r"[a-z0-9]+(?:[-.,/][a-z0-9]+)*")
_PART_SEPARATOR = re.compile(r"[-./,]")
_STOPWORDS = frozenset(
    "a al ante con de del desde durante e el en entre la las lo los o para por que se sin "
    "sobre su sus un una uno unos unas y es son como cual cuales cuando donde este esta estos "
    "estas ese esa no si qué".split()
)


class LexicalTokenizer:
    def tokenize(self, text: str) -> list[str]:
        """Return tokens without stopwords; a compound token also yields its parts."""
        tokens: list[str] = []
        for token in _TOKEN.findall(self._normalize(text)):
            if token in _STOPWORDS:
                continue
            tokens.append(token)
            parts = _PART_SEPARATOR.split(token)
            if len(parts) > 1:
                tokens.extend(part for part in parts if part not in _STOPWORDS)
        return tokens

    def document_vector(self, text: str, average_length: float) -> tuple[list[int], list[float]]:
        """Build a sparse vector whose values are the BM25 term-frequency weights."""
        tokens = self.tokenize(text)
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1

        length_ratio = len(tokens) / average_length
        weights = {
            self._index(token): count * (_K1 + 1) / (count + _K1 * (1 - _B + _B * length_ratio))
            for token, count in counts.items()
        }
        return list(weights), list(weights.values())

    def query_vector(self, text: str) -> tuple[list[int], list[float]]:
        """Build a sparse query vector with unit weights. Compound tokens stay whole, so
        "VA-AY-003" does not match every document containing "003"."""
        tokens = _TOKEN.findall(self._normalize(text))
        indices = {self._index(token) for token in tokens if token not in _STOPWORDS}
        return list(indices), [1.0] * len(indices)

    def _index(self, token: str) -> int:
        """Stable across processes, unlike Python's built-in hash()."""
        return zlib.crc32(token.encode("utf-8"))

    def _normalize(self, text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text)
        return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()
