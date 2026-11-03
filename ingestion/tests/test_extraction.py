from dataclasses import replace

import pytest

from app.config.Settings import settings
from app.models.ExtractedDocument import UNVERSIONED
from app.repositories.MarkdownRepository import MarkdownRepository
from app.repositories.PdfRepository import PdfRepository
from app.repositories.RegistryRepository import RegistryRepository
from app.services.ExtractionVerifier import ExtractionVerifier
from app.services.SectionParser import SectionParser

PDF_PATHS = sorted(settings.corpus_pdf_dir.rglob("*.pdf"))


def extract(relative_path: str):
    return SectionParser().parse(relative_path, PdfRepository().read(settings.corpus_pdf_dir / relative_path))


def read_markdown(relative_path: str):
    path = (settings.corpus_md_dir / relative_path).with_suffix(".md")
    return MarkdownRepository().read(path)


@pytest.fixture(scope="module")
def verifier() -> ExtractionVerifier:
    return ExtractionVerifier(RegistryRepository(settings.validity_registry_path).load())


def test_corpus_has_nineteen_documents():
    assert len(PDF_PATHS) == 19


@pytest.mark.parametrize("path", PDF_PATHS, ids=lambda path: path.stem)
def test_extraction_matches_markdown_and_registry(path, verifier):
    relative_path = path.relative_to(settings.corpus_pdf_dir).as_posix()
    issues = verifier.verify(extract(relative_path), read_markdown(relative_path))
    assert issues == []


def test_verifier_detects_altered_area(verifier):
    relative_path = "01_manuales/MAN-OPE-001_v3.pdf"
    document = extract(relative_path)
    altered = replace(document, metadata=replace(document.metadata, issuing_area="Otra"))
    fields = {issue.field for issue in verifier.verify(altered, read_markdown(relative_path))}
    assert {"registry.authority", "issuing_area"} <= fields


def test_verifier_detects_altered_section_text(verifier):
    relative_path = "03_normativa/RES-CREG-0043-2024.pdf"
    document = extract(relative_path)
    section = document.sections[1]
    block = replace(section.blocks[0], text="0,5 %")
    altered_section = replace(section, blocks=(block,))
    altered = replace(document, sections=(document.sections[0], altered_section, *document.sections[2:]))
    fields = {issue.field for issue in verifier.verify(altered, read_markdown(relative_path))}
    assert f"section:{section.heading}" in fields


def test_header_cell_spanning_two_lines_is_not_mixed():
    metadata = extract("01_manuales/MAN-OPE-001_v3.pdf").metadata
    assert metadata.issuing_area == "Vicepresidencia de Transporte — Operaciones"
    assert metadata.replaces == "MAN-OPE-001 v2"


def test_resolution_uses_articles_and_has_no_version():
    document = extract("03_normativa/RES-CREG-0043-2024.pdf")
    assert document.metadata.version == UNVERSIONED
    assert document.sections[1].section_id == "art-2"


def test_table_before_first_numeral_has_no_numeral():
    sections = extract("02_procedimientos/PRO-MED-007_v2.pdf").sections
    criteria = next(section for section in sections if section.section_id == "3")
    assert criteria.blocks[0].kind == "table"
    assert criteria.blocks[0].numeral is None
    assert [block.numeral for block in criteria.blocks[1:]] == ["3.1", "3.2", "3.3"]


def test_table_after_numeral_belongs_to_it():
    sections = extract("02_procedimientos/PRO-OPE-012_v3.pdf").sections
    criteria = next(section for section in sections if section.section_id == "3")
    assert criteria.blocks[1].kind == "table"
    assert criteria.blocks[1].numeral == "3.1"


def test_annex_is_a_separate_section():
    sections = extract("05_comunicaciones/COM-PRV-0134.pdf").sections
    annex = sections[-1]
    assert annex.section_id == "anexo-notas-de-integracion"
    assert "INSTRUCCIÓN" in annex.blocks[0].text
    assert all("INSTRUCCIÓN" not in block.text for section in sections[:-1] for block in section.blocks)
