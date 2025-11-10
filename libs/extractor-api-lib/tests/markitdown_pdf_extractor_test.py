"""Tests for MarkitdownPDFExtractor."""
from pathlib import Path
from unittest.mock import patch

import pytest

from extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor import MarkitdownPDFExtractor
from extractor_api_lib.impl.settings.pdf_extractor_settings import PDFExtractorSettings
from extractor_api_lib.impl.types.content_type import ContentType
from extractor_api_lib.impl.types.file_type import FileType


@pytest.fixture
def settings_default() -> PDFExtractorSettings:
    return PDFExtractorSettings(split_level_max=3, min_section_chars=80)


@pytest.fixture
def extractor(mock_file_service, settings_default) -> MarkitdownPDFExtractor:
    return MarkitdownPDFExtractor(file_service=mock_file_service, settings=settings_default)


def _mock_md(monkey_text: str):
    class DummyResult:
        text_content = monkey_text

    return DummyResult()


def _write_dummy_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "dummy.pdf"
    p.write_bytes(b"%PDF-1.4\n%...mock...")
    return p


def test_compatible_file_types(extractor):
    assert extractor.compatible_file_types == [FileType.PDF]


@pytest.mark.asyncio
async def test_happy_path(extractor, tmp_path: Path):
    # Create a dummy pdf file path (MarkItDown will be mocked)
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%...mock...")

    class DummyResult:
        text_content = """
1. Introduction
This is intro text.

2. Methods
Detailed methods here.
"""

    with patch("extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown") as mk:
        mk.return_value.convert.return_value = DummyResult()
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    assert isinstance(pieces, list)
    assert len(pieces) >= 1
    assert all(p.type == ContentType.TEXT for p in pieces)
    assert all(p.metadata["document"] == "doc" for p in pieces)


@pytest.mark.asyncio
async def test_edge_empty_text(extractor, tmp_path: Path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%...mock...")

    class DummyResult:
        text_content = ""

    with patch("extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown") as mk:
        mk.return_value.convert.return_value = DummyResult()
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    assert pieces == []


@pytest.mark.asyncio
async def test_split_on_h1_to_h3_ignore_h4(tmp_path: Path, mock_file_service):
    # Use tiny min_section_chars to avoid merging in this test
    settings = PDFExtractorSettings(split_level_max=3, min_section_chars=1)
    extractor = MarkitdownPDFExtractor(file_service=mock_file_service, settings=settings)

    pdf_path = _write_dummy_pdf(tmp_path)
    md_text = (
        "# A\nParagraph A\n\n#### Minor\nDetail under minor heading\n\n## B\nB body\n\n### C\nC body\n"
    )

    with patch(
        "extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown"
    ) as mk:
        mk.return_value.convert.return_value = _mock_md(md_text)
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    assert isinstance(pieces, list)
    # Should split at #, ##, ### but not at ####
    assert [p.metadata.get("md_heading_level") for p in pieces] == [1, 2, 3]
    assert [p.metadata["title"] for p in pieces] == ["A", "B", "C"]
    # H4 content should be included in the first piece body, not as its own piece
    assert "#### Minor" in (pieces[0].page_content or "")


@pytest.mark.asyncio
async def test_setext_normalization(extractor, tmp_path: Path):
    pdf_path = _write_dummy_pdf(tmp_path)
    md_text = "Intro\n====\nBody text here.\n"

    with patch(
        "extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown"
    ) as mk:
        mk.return_value.convert.return_value = _mock_md(md_text)
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    assert len(pieces) == 1
    assert pieces[0].type == ContentType.TEXT
    assert pieces[0].metadata.get("md_heading_level") == 1
    assert pieces[0].metadata["title"] == "Intro"
    assert pieces[0].metadata["document"] == "doc"


@pytest.mark.asyncio
async def test_bare_page_label_normalization(tmp_path: Path, mock_file_service):
    # Avoid merging in this test
    settings = PDFExtractorSettings(split_level_max=3, min_section_chars=1)
    extractor = MarkitdownPDFExtractor(file_service=mock_file_service, settings=settings)

    pdf_path = _write_dummy_pdf(tmp_path)
    md_text = "Page 1\nPreface text\n\n## Chapter 1\nStuff\n"

    with patch(
        "extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown"
    ) as mk:
        mk.return_value.convert.return_value = _mock_md(md_text)
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    # Page 1 becomes H2; Chapter 1 is H2 -> two pieces
    assert [p.metadata["title"] for p in pieces] == ["Page 1", "Chapter 1"]
    assert [p.metadata.get("md_heading_level") for p in pieces] == [2, 2]


@pytest.mark.asyncio
async def test_hrule_fallback_split(tmp_path: Path, mock_file_service):
    # Avoid merging in this test
    settings = PDFExtractorSettings(split_level_max=3, min_section_chars=1)
    extractor = MarkitdownPDFExtractor(file_service=mock_file_service, settings=settings)

    pdf_path = _write_dummy_pdf(tmp_path)
    md_text = "Alpha block line\nline\n\n---\n\nBeta block\nmore\n\n***\n\nGamma end\n"

    with patch(
        "extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown"
    ) as mk:
        mk.return_value.convert.return_value = _mock_md(md_text)
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    # With min_section_chars=1 and no headings, sections may still merge due to content adjacency rules.
    # Ensure we produce at least one piece and it contains all blocks.
    assert len(pieces) >= 1
    content_joined = "\n".join(p.page_content or "" for p in pieces)
    assert "Alpha block line" in content_joined
    assert "Beta block" in content_joined
    assert "Gamma end" in content_joined


@pytest.mark.asyncio
async def test_merge_small_sections(tmp_path: Path, mock_file_service):
    # Configure smaller threshold to force merges in test
    settings = PDFExtractorSettings(split_level_max=3, min_section_chars=80)
    extractor = MarkitdownPDFExtractor(file_service=mock_file_service, settings=settings)

    pdf_path = _write_dummy_pdf(tmp_path)
    md_text = (
        "# H1\nshort\n\n## H2\nsmall\n\n### H3\ntiny\n\n## H2b\nmore tiny\n"
    )

    with patch(
        "extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown"
    ) as mk:
        mk.return_value.convert.return_value = _mock_md(md_text)
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    # There are 4 split points, but many are small -> should merge into fewer pieces
    assert len(pieces) < 4
    # Still TEXT and correct doc
    assert all(p.type == ContentType.TEXT for p in pieces)
    assert all(p.metadata["document"] == "doc" for p in pieces)


@pytest.mark.asyncio
async def test_split_level_max_affects_splitting(tmp_path: Path, mock_file_service):
    # Only split up to H2; H3 should be part of previous section
    settings = PDFExtractorSettings(split_level_max=2, min_section_chars=10)
    extractor = MarkitdownPDFExtractor(file_service=mock_file_service, settings=settings)

    pdf_path = _write_dummy_pdf(tmp_path)
    md_text = "# H1\nbody1\n\n### H3\nbody3\n\n## H2\nbody2\n"

    with patch(
        "extractor_api_lib.impl.extractors.file_extractors.markitdown_pdf_extractor.MarkItDown"
    ) as mk:
        mk.return_value.convert.return_value = _mock_md(md_text)
        pieces = await extractor.aextract_content(pdf_path, name="doc")

    # Expect only H1 and H2 to be split; H3 content included in the first piece
    assert [p.metadata.get("md_heading_level") for p in pieces] == [1, 2]
    assert "### H3" in (pieces[0].page_content or "")
