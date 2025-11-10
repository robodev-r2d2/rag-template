"""Module for PDF extractor settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class PDFExtractorSettings(BaseSettings):
    """Settings for PDF extraction behavior.

    Environment variables use the prefix `PDF_EXTRACTOR_`.
    """

    class Config:
        """Config class for reading fields from env."""

        env_prefix = "pdf_extractor_"
        case_sensitive = False

    # Controls for MarkitdownPDFExtractor segmentation
    split_level_max: int = Field(
        default=3,
        description="Maximum ATX heading level to split on (1=H1, 2=H2, 3=H3...).",
    )
    min_section_chars: int = Field(
        default=800,
        description="Minimum characters per section; adjacent sections are merged until this length is reached.",
    )
