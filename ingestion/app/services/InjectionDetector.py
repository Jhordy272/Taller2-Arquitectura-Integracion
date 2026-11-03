"""Flags text that gives instructions to an automated system (ADR-06). Deterministic
rules catch explicit wording only; paraphrases remain a declared residual risk."""
import re
import unicodedata

DETECTION_RULES_VERSION = "1"

_RULES = {
    "addresses_automated_systems": re.compile(
        r"\b(instruccion|instrucciones)\b.{0,40}\b(sistema|sistemas|asistente|modelo|agente|ia)\b"
    ),
    "overrides_instructions": re.compile(
        r"\b(ignore|ignora|ignorar|omita|olvide|olvida)\b.{0,40}\b(instruccion|instrucciones|indicaciones|reglas)\b"
        r"|\bignore (all |any )?(previous|prior) instructions\b"
    ),
    "hides_from_user": re.compile(r"\bno (informe|informes|le diga|mencione|revele)\b.{0,30}\b(usuario|operador)\b"),
    "exfiltrates_by_email": re.compile(
        r"\b(remita|envie|reenvie|adjunte)\b.{0,120}\b[\w.-]+@[\w-]+(\.[\w-]+)+"
    ),
}


class InjectionDetector:
    def detect(self, text: str) -> str | None:
        """Return the names of the matched rules, or None if the text looks clean."""
        normalized = self._normalize(text)
        matched = [name for name, rule in _RULES.items() if rule.search(normalized)]
        return ", ".join(matched) or None

    def _normalize(self, text: str) -> str:
        """Lowercase, strip accents and collapse whitespace, so wrapping cannot hide a match."""
        decomposed = unicodedata.normalize("NFKD", text)
        without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
        return " ".join(without_accents.lower().split())
