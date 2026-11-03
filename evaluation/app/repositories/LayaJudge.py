"""Judges anchoring and relevance with laya typed decisions, locally. Uses the
multilingual checkpoint in a pinned revision because the corpus is in Spanish."""
from laya import Router

_RELEVANCE_CRITERIA = {
    "relevante": "El pasaje contiene la respuesta a la pregunta.",
    "relacionado": "El pasaje trata el mismo tema, pero no contiene la respuesta.",
    "no_relevante": "El pasaje trata otro tema.",
}


class LayaJudge:
    def __init__(self, model: str, revision: str) -> None:
        self._model = model
        self._router = Router(standalone_repos=True, revisions={model: revision})

    def anchored(self, passage_text: str, expected_answer: str) -> float:
        """Return P(true) that the text supports the statement (noul type)."""
        result = self._router.predict(
            {"pasaje": passage_text, "afirmacion": expected_answer},
            {"anclaje": {"type": "noul", "instructions": "¿El pasaje sustenta la afirmación?"}},
            model=self._model,
        )
        return result["answers"]["anclaje"]["noul"]

    def is_relevant(self, question: str, passage_text: str) -> bool:
        """Classify one passage against the question (choice type)."""
        result = self._router.predict(
            {"pregunta": question, "pasaje": passage_text},
            {
                "pertinencia": {
                    "type": "choice",
                    "instructions": "¿Qué tan pertinente es el pasaje para responder la pregunta?",
                    "criteria": _RELEVANCE_CRITERIA,
                }
            },
            model=self._model,
        )
        return result["answers"]["pertinencia"]["choice"] == "relevante"
