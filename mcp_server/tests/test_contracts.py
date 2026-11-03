"""Checks that need neither Qdrant nor the embedding model."""
from pathlib import Path

import pytest

from app.models.RetrievedFragment import RetrievedFragment
from app.repositories.QdrantSearchRepository import stable_order
from app.services.HybridSearchService import IncompatibleCollectionError, ensure_compatible
from app.services.LexicalTokenizer import TOKENIZER_VERSION

COMPONENTS = Path(__file__).resolve().parents[2]
METADATA = {
    "embedding_model": "model",
    "embedding_revision": "abc",
    "embedding_dimensions": 384,
    "tokenizer_version": TOKENIZER_VERSION,
}


def fragment(fragment_id: str, score: float) -> RetrievedFragment:
    return RetrievedFragment(
        fragment_id=fragment_id, score=score, code="C", version="1", title="T", document_type="D",
        document_class="record", issue_date="2025-01-01", issuing_area="A", section_id="1",
        section_title="S", parent_section_id=None, text="x", indexed_text="x",
        validity_status="valid", injection_risk=False,
    )


def test_ties_are_broken_by_id_whatever_the_incoming_order():
    first, second, best = fragment("A@1#1", 0.5), fragment("B@1#1", 0.5), fragment("Z@1#1", 0.9)
    assert stable_order([second, best, first]) == [best, first, second]
    assert stable_order([first, second, best]) == [best, first, second]


def test_tokenizer_is_identical_to_the_one_used_at_ingestion():
    path = "app/services/LexicalTokenizer.py"
    assert (COMPONENTS / "mcp_server" / path).read_text("utf-8") == (COMPONENTS / "ingestion" / path).read_text("utf-8")


def test_compatible_collection_is_accepted():
    ensure_compatible(METADATA, "model", "abc", 384)


@pytest.mark.parametrize(
    "model, revision, dimensions",
    [("other", "abc", 384), ("model", "other", 384), ("model", "abc", 768)],
)
def test_incompatible_collection_is_rejected(model, revision, dimensions):
    with pytest.raises(IncompatibleCollectionError):
        ensure_compatible(METADATA, model, revision, dimensions)


def test_collection_without_metadata_is_rejected():
    with pytest.raises(IncompatibleCollectionError):
        ensure_compatible({}, "model", "abc", 384)
