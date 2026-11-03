"""Ingestion entry point: extracts and verifies every corpus PDF, partitions the
documents that pass, and indexes the fragments. --activate switches the active alias;
--baseline builds the fixed-size collection used only to compare partitions;
--sync-validity only propagates the registry to the active collection."""
import argparse
import logging
import sys
import time

from app.config.Settings import settings
from app.models.ExtractedDocument import ExtractedDocument
from app.models.Fragment import Fragment
from app.repositories.EmbeddingRepository import EmbeddingRepository
from app.repositories.MarkdownRepository import MarkdownRepository
from app.repositories.PdfRepository import PdfRepository
from app.repositories.QdrantRepository import QdrantRepository
from app.repositories.RegistryRepository import RegistryRepository
from app.services.ExtractionVerifier import ExtractionVerifier
from app.services.FixedSizePartitioner import FixedSizePartitioner
from app.services.InjectionDetector import DETECTION_RULES_VERSION, InjectionDetector
from app.services.LexicalTokenizer import TOKENIZER_VERSION, LexicalTokenizer
from app.services.Partitioner import PARTITION_VERSION, Partitioner
from app.services.SectionParser import SectionParser

logging.basicConfig(level=logging.INFO)
for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger("ingestion")

BASELINE_COLLECTION = "corpus_baseline_fixed_size"


def extract_verified_documents(registry: list[dict]) -> tuple[list[ExtractedDocument], int]:
    """Return the documents that pass verification; the others are not indexed."""
    pdf_repository = PdfRepository()
    markdown_repository = MarkdownRepository()
    parser = SectionParser()
    verifier = ExtractionVerifier(registry)

    documents: list[ExtractedDocument] = []
    rejected = 0
    for path in sorted(settings.corpus_pdf_dir.rglob("*.pdf")):
        relative_path = path.relative_to(settings.corpus_pdf_dir)
        document = parser.parse(relative_path.as_posix(), pdf_repository.read(path))
        markdown = markdown_repository.read((settings.corpus_md_dir / relative_path).with_suffix(".md"))
        issues = verifier.verify(document, markdown)
        for issue in issues:
            logger.error("%s | %s\n  expected: %s\n  actual:   %s", issue.source, issue.field, issue.expected, issue.actual)
        if issues:
            rejected += 1
        else:
            documents.append(document)
    return documents, rejected


def collection_name() -> str:
    """Name a collection after everything that determines its vectors (ADR-04)."""
    model = settings.embedding_model.rsplit("/", 1)[-1]
    return (
        f"corpus__{model}__{settings.embedding_revision[:8]}"
        f"__p{PARTITION_VERSION}__t{TOKENIZER_VERSION}__d{DETECTION_RULES_VERSION}"
    )


def index_fragments(fragments: list[Fragment], embeddings: EmbeddingRepository, name: str) -> QdrantRepository:
    tokenizer = LexicalTokenizer()
    texts = [fragment.indexed_text for fragment in fragments]
    average_length = sum(len(tokenizer.tokenize(text)) for text in texts) / len(texts)

    qdrant = QdrantRepository(settings.qdrant_url)
    qdrant.ensure_collection(
        name,
        settings.embedding_dimensions,
        metadata={
            "embedding_model": settings.embedding_model,
            "embedding_revision": settings.embedding_revision,
            "embedding_dimensions": settings.embedding_dimensions,
            "partition_version": PARTITION_VERSION,
            "tokenizer_version": TOKENIZER_VERSION,
            "detection_rules_version": DETECTION_RULES_VERSION,
        },
    )
    qdrant.replace_points(
        name,
        fragments,
        embeddings.embed_passages(texts),
        [tokenizer.document_vector(text, average_length) for text in texts],
    )
    return qdrant


def sync_validity() -> int:
    """Propagate a validity change: payload only, without reading PDFs or recomputing vectors."""
    registry = RegistryRepository(settings.validity_registry_path)
    started = time.perf_counter()
    documents, unregistered = QdrantRepository(settings.qdrant_url).sync_validity(
        settings.active_alias, registry.load(), registry.default_status()
    )
    elapsed = time.perf_counter() - started
    logger.info("synchronized %d documents in %.2f s; not in the registry: %s", documents, elapsed, unregistered or "none")
    logger.info("restart mcp_server so that it reads the new registry")
    return 0


def run(activate: bool, baseline: bool) -> int:
    registry = RegistryRepository(settings.validity_registry_path).load()
    documents, rejected = extract_verified_documents(registry)

    partitioner = (FixedSizePartitioner if baseline else Partitioner)(registry, InjectionDetector())
    fragments = [fragment for document in documents for fragment in partitioner.partition(document)]
    for fragment in fragments:
        if fragment.injection_risk:
            logger.warning("injection risk: %s (%s)", fragment.fragment_id, fragment.injection_reason)

    embeddings = EmbeddingRepository(settings.embedding_model, settings.embedding_revision)
    too_long = [f.fragment_id for f in fragments if embeddings.token_count(f.indexed_text) > embeddings.max_tokens]
    if too_long:
        logger.error("fragments over the model limit of %d tokens: %s", embeddings.max_tokens, too_long)
        return 1

    name = BASELINE_COLLECTION if baseline else collection_name()
    qdrant = index_fragments(fragments, embeddings, name)

    active = qdrant.active_collection(settings.active_alias)
    if not baseline and (active is None or activate):
        qdrant.activate(settings.active_alias, name)
        active = name

    logger.info(
        "%d documents, %d rejected, %d fragments in %s; active collection: %s",
        len(documents), rejected, len(fragments), name, active,
    )
    return 1 if rejected else 0


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--activate", action="store_true", help="switch the active alias to the new collection")
    arguments.add_argument("--baseline", action="store_true", help="build the fixed-size comparison collection")
    arguments.add_argument("--sync-validity", action="store_true", help="only propagate the registry to the active collection")
    parsed = arguments.parse_args()
    sys.exit(sync_validity() if parsed.sync_validity else run(parsed.activate, parsed.baseline))
