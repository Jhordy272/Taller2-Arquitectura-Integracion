"""Support check for natural-language questions, adopted against "no sé" (P3 experiment).
The cosine threshold says a passage is near the question, not that it covers it: a question
close to the corpus vocabulary passes it with a passage about something else. The guard
also asks the passage to mention most of what was asked. Set by answer_guard."""
from app.services.LexicalTokenizer import LexicalTokenizer

# Question words carry no topic: they must not count as terms the passage has to mention.
_QUESTION_WORDS = frozenset(
    "cual cuales cuanto cuantos cuanta cuantas que quien quienes hace hacer debe deben puede pueden "
    "hay tiene tienen cada".split()
)
# Light stemming: "investigan" matches "investigacion", "valvulas" matches "valvula".
_STEM_LENGTH = 5
_MIN_TERM_LENGTH = 3


class LexicalGuard:
    def __init__(self, tokenizer: LexicalTokenizer, min_coverage: float) -> None:
        self._tokenizer = tokenizer
        self._min_coverage = min_coverage

    def query_terms(self, query: str) -> list[str]:
        return [
            term
            for term in dict.fromkeys(self._tokenizer.tokenize(query))
            if term not in _QUESTION_WORDS and len(term) >= _MIN_TERM_LENGTH
        ]

    def coverage(self, query: str, passage_text: str) -> float:
        terms = self.query_terms(query)
        if not terms:
            return 1.0
        stems = {term[:_STEM_LENGTH] for term in self._tokenizer.tokenize(passage_text)}
        return sum(term[:_STEM_LENGTH] in stems for term in terms) / len(terms)

    def supports(self, query: str, passage_text: str) -> bool:
        return self.coverage(query, passage_text) >= self._min_coverage
