"""Markitdown-based PDF extractor.

# Assumptions:
# - "context7" was mentioned by the user but not found in the repository; proceeding without it.
# - We only extract TEXT content with MarkItDown; tables are left embedded in Markdown text.
# - Keep behavior consistent with other extractors (absolute imports, typing, logging).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from markitdown import MarkItDown

from extractor_api_lib.extractors.information_file_extractor import InformationFileExtractor
from extractor_api_lib.file_services.file_service import FileService
from extractor_api_lib.impl.types.content_type import ContentType
from extractor_api_lib.impl.types.file_type import FileType
from extractor_api_lib.impl.utils.utils import hash_datetime
from extractor_api_lib.models.dataclasses.internal_information_piece import InternalInformationPiece
from extractor_api_lib.impl.settings.pdf_extractor_settings import PDFExtractorSettings

logger = logging.getLogger(__name__)


class MarkitdownPDFExtractor(InformationFileExtractor):
    """Extractor that uses MarkItDown to convert PDFs to Markdown and emits text pieces.

    Notes
    -----
    - Produces `ContentType.TEXT` items only.
    - Splits content using Markdown heading patterns (ATX, with basic Setext support).
    - Also recognizes horizontal rules and bare "Page N" labels as section boundaries.
    - Avoids over-segmentation by only splitting at H1–H3 and merging small sections.
    """

    # Markdown heading patterns
    MD_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
    # Basic Setext (underlined) heading support; we'll normalize these to ATX during processing
    MD_SETEXT_HEADING = re.compile(r"^(?P<title>[^\n][\s\S]*?)\n(?P<underline>=+|-+)\s*$", re.MULTILINE)
    # Horizontal rule (section delimiter)
    MD_HRULE = re.compile(r"^\s{0,3}(?:-{3,}|_{3,}|\*{3,})\s*$", re.MULTILINE)
    # Bare page label like "Page 1" (common in PDF conversions). We'll convert to an ATX heading.
    MD_BARE_PAGE_LABEL = re.compile(r"^(?:Page)\s+(\d{1,4})\b.*$", re.MULTILINE)

    # Heuristics to avoid tiny chunks
    SPLIT_LEVEL_MAX = 3  # only split on H1–H3
    MIN_SECTION_CHARS = 800  # merge adjacent sections until at least this many characters

    def __init__(self, file_service: FileService, settings: PDFExtractorSettings):
        """Initialize the MarkitdownPDFExtractor.

        Parameters
        ----------
        file_service : FileService
            Handler for downloading the file to extract content from and upload results to if required.
        """
        super().__init__(file_service=file_service)
        self._split_level_max = max(1, int(settings.split_level_max))
        self._min_section_chars = max(1, int(settings.min_section_chars))

    @property
    def compatible_file_types(self) -> list[FileType]:
        """List of compatible file types for this extractor (PDF only)."""
        return [FileType.PDF]

    async def aextract_content(self, file_path: Path, name: str) -> list[InternalInformationPiece]:
        """Extract content from the given PDF using MarkItDown.

        Parameters
        ----------
        file_path : Path
            Path to the PDF file.
        name : str
            Document name.
        """
        try:
            md = MarkItDown(enable_plugins=False)
            result = md.convert(file_path.as_posix())
            text_content = getattr(result, "text_content", "") or ""
        except Exception as e:
            logger.warning("MarkItDown conversion failed for %s: %s", file_path, e)
            return []

        if not text_content.strip():
            return []

        return self._process_text_content(content=text_content, title="", page_index=1, document_name=name)

    def _normalize_setext(self, content: str) -> str:
        """Normalize Setext headings to ATX style for simpler splitting.

        Converts lines like:
        Title\n====
        to
        # Title
        """
        def repl(match: re.Match) -> str:
            title = match.group("title").strip()
            underline = match.group("underline")
            level = 1 if underline.startswith("=") else 2
            return f"{'#' * level} {title}"

        return re.sub(self.MD_SETEXT_HEADING, repl, content)

    def _normalize_page_labels(self, content: str) -> str:
        """Convert bare page labels like 'Page 3' to ATX headings (## Page 3).

        This helps create section boundaries when MarkItDown emits page labels
        without heading markers.
        """
        def repl(match: re.Match) -> str:
            num = match.group(1)
            return f"## Page {num}"

        return re.sub(self.MD_BARE_PAGE_LABEL, repl, content)

    def _split_by_hr(self, content: str) -> list[str]:
        """Split content by horizontal rules, returning non-empty trimmed sections."""
        parts = [p.strip() for p in re.split(self.MD_HRULE, content) if p and p.strip()]
        return parts

    def _first_line_as_title(self, text: str) -> str:
        for line in text.splitlines():
            if line.strip():
                return line.strip()[:120]
        return ""

    def _merge_small_sections(self, pieces: list[InternalInformationPiece]) -> list[InternalInformationPiece]:
        if not pieces:
            return pieces
        merged: list[InternalInformationPiece] = []
        for piece in pieces:
            if not merged:
                merged.append(piece)
                continue
            prev = merged[-1]
            if (len(prev.page_content or "") < self._min_section_chars) or (
                len((prev.page_content or "")) + len((piece.page_content or "")) < self._min_section_chars
            ):
                # Merge into previous; keep previous title
                prev.page_content = ((prev.page_content or "").rstrip() + "\n\n" + (piece.page_content or "").lstrip()).strip()
                # Optionally, carry over md_heading_level of the earliest (kept as-is)
                continue
            merged.append(piece)
        return merged

    def _process_text_content(
        self, content: str, title: str, page_index: int, document_name: str
    ) -> list[InternalInformationPiece]:
        """Split Markdown content into information pieces using heading detection.

        Parameters
        ----------
        content : str
            Markdown content returned by MarkItDown.
        title : str
            Current title context (unused here).
        page_index : int
            We do not have page granularity from MarkItDown; use 1 for the whole doc.
        document_name : str
            Name of the document.
        """
        raw_items: list[InternalInformationPiece] = []
        if not content or not content.strip():
            return raw_items

        content = self._normalize_setext(content)
        content = self._normalize_page_labels(content)

        # Identify only split points at H1–H3
        all_headings = list(self.MD_ATX_HEADING.finditer(content))
        split_points = [m for m in all_headings if len(m.group(1)) <= self._split_level_max]

        if not split_points:
            # Fallback 1: split by horizontal rules
            sections = self._split_by_hr(content)
            if not sections:
                # No clear boundaries; single piece
                raw_items.append(
                    self._create_information_piece(
                        document_name=document_name,
                        page=page_index,
                        title="",
                        content=content.strip(),
                        content_type=ContentType.TEXT,
                        information_id=hash_datetime(),
                    )
                )
                return self._merge_small_sections(raw_items)

            for sec in sections:
                sec_title = self._first_line_as_title(sec)
                raw_items.append(
                    self._create_information_piece(
                        document_name=document_name,
                        page=page_index,
                        title=sec_title,
                        content=sec,
                        content_type=ContentType.TEXT,
                        information_id=hash_datetime(),
                    )
                )
            return self._merge_small_sections(raw_items)

        # Build sections by split points (keep minor headings as part of body)
        for idx, m in enumerate(split_points):
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            start = m.end()
            end = split_points[idx + 1].start() if idx + 1 < len(split_points) else len(content)
            body = content[start:end].strip()

            full_content = f"{'#' * level} {heading_text}\n{body}" if body else f"{'#' * level} {heading_text}"

            raw_items.append(
                self._create_information_piece(
                    document_name=document_name,
                    page=page_index,
                    title=heading_text,
                    content=full_content,
                    content_type=ContentType.TEXT,
                    information_id=hash_datetime(),
                    additional_meta={"md_heading_level": level},
                )
            )

        return self._merge_small_sections(raw_items)

    @staticmethod
    def _create_information_piece(
        document_name: str,
        page: int,
        title: str,
        content: str,
        content_type: ContentType,
        information_id: str,
        additional_meta: Optional[dict] = None,
        related_ids: Optional[list[str]] = None,
    ) -> InternalInformationPiece:
        metadata = {
            "document": document_name,
            "page": page,
            "title": title,
            "id": information_id,
            "related": related_ids if related_ids else [],
        }
        if additional_meta:
            metadata = metadata | additional_meta
        return InternalInformationPiece(
            type=content_type,
            metadata=metadata,
            page_content=content,
        )
