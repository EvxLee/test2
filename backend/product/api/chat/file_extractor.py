"""
Text extraction from file bytes.

Supports PDF (with OCR fallback for scanned documents), DOCX, and PPTX.
Returns a list of TextSegment objects, each carrying the text of one logical
unit (page, slide, or heading section) along with its page number and section
title where available.

Usage:
    segments = extract_text(file_bytes, "report.pdf")
    segments = extract_text(file_bytes, "notes.docx")
    segments = extract_text(file_bytes, "deck.pptx")
    # Returns None if the file type is unsupported or extraction fails.
"""

import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Scanned PDF detection: if the average extracted characters per page falls
# below this threshold, the PDF is likely a scanned image and needs OCR.
_OCR_CHARS_PER_PAGE_THRESHOLD = 20

# Claude Haiku — cheapest Bedrock vision model
_DEFAULT_OCR_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Module-level import so BedrockLLMClient can be patched in tests.
from .llm_client import BedrockLLMClient  # noqa: E402


@dataclass
class TextSegment:
    """One logical unit of extracted text with positional metadata."""
    text: str
    page_number: int | None = None    # PDF page, PPTX slide number; None for DOCX
    section_title: str | None = None  # PPTX slide title, DOCX heading; None if unavailable


def _get_ocr_model_id() -> str:
    """Resolve the Bedrock OCR model ID from environment."""
    return os.getenv("BEDROCK_OCR_MODEL_ID", _DEFAULT_OCR_MODEL_ID)


def extract_text(file_bytes: bytes, file_name: str) -> list[TextSegment] | None:
    """
    Extract plain text from file bytes as a list of TextSegments.

    Each segment represents one logical unit: a PDF page, a PPTX slide, or a
    DOCX heading section. For PDFs, falls back to Claude Haiku OCR when
    pdfplumber yields sparse text (indicating a scanned document).

    Returns None if the file type is unsupported or extraction produces
    no usable text.

    Args:
        file_bytes: Raw bytes of the file.
        file_name:  Original file name, used to determine file type.

    Returns:
        List of TextSegment objects, or None on failure / unsupported type.
    """
    ext = Path(file_name).suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(file_bytes, file_name)
    elif ext == ".docx":
        return _extract_docx(file_bytes, file_name)
    elif ext == ".pptx":
        return _extract_pptx(file_bytes, file_name)
    else:
        logger.warning(f"Unsupported file type '{ext}' for file: {file_name}")
        return None


def _extract_pdf(file_bytes: bytes, file_name: str) -> list[TextSegment] | None:
    """
    Extract text from PDF bytes using pdfplumber, one segment per page.

    If the extracted text is sparse (avg < _OCR_CHARS_PER_PAGE_THRESHOLD
    chars/page), the PDF is treated as scanned and _extract_pdf_ocr() is
    called as a fallback.
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber is not installed. Run: pip install pdfplumber")
        return None

    try:
        segments: list[TextSegment] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            num_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""

                # Extract tables and append pipe-delimited rows so structured
                # data (e.g. rate tables) survives chunking with readable format.
                table_lines: list[str] = []
                try:
                    for table in (page.extract_tables() or []):
                        for row in (table or []):
                            cells = [str(c).strip() if c is not None else "" for c in row]
                            cells = [c for c in cells if c]
                            if cells:
                                table_lines.append(" | ".join(cells))
                except Exception:
                    pass  # table extraction is best-effort

                combined = text.strip()
                if table_lines:
                    table_block = "\n".join(table_lines)
                    # Avoid pure duplication: only append if the pipe-formatted
                    # version isn't already present (extract_text rarely produces "|")
                    if "|" not in combined:
                        combined = (combined + "\n\n" + table_block).strip() if combined else table_block

                if combined:
                    segments.append(TextSegment(
                        text=combined,
                        page_number=page_num,
                        section_title=None,
                    ))

        total_chars = sum(len(s.text) for s in segments)
        avg_chars = total_chars / num_pages if num_pages else 0

        if avg_chars < _OCR_CHARS_PER_PAGE_THRESHOLD:
            logger.info(
                f"Sparse text in '{file_name}' "
                f"({avg_chars:.0f} chars/page avg) — falling back to OCR"
            )
            return _extract_pdf_ocr(file_bytes, file_name)

        if not segments:
            logger.warning(f"No text extracted from PDF: {file_name}")
            return None

        return segments

    except Exception as e:
        logger.error(f"PDF extraction failed for {file_name}: {e}")
        return None


def _extract_pdf_ocr(file_bytes: bytes, file_name: str) -> list[TextSegment] | None:
    """
    OCR fallback for scanned PDFs using Claude Haiku via AWS Bedrock.

    Converts each PDF page to a PNG image at 200 DPI and sends it to the
    model with a verbatim text-extraction prompt via the Converse API image
    content block format.

    Requires:
        - pdf2image Python package  (pip install pdf2image)
        - poppler-utils system package  (apt-get install poppler-utils)
        - AWS Bedrock access for the Haiku model
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        logger.error(
            "pdf2image is not installed. "
            "Run: pip install pdf2image  (also requires poppler-utils)"
        )
        return None

    try:
        ocr_client = BedrockLLMClient(model_id=_get_ocr_model_id())
    except Exception as e:
        logger.error(f"Could not initialise OCR client: {e}")
        return None

    try:
        images = convert_from_bytes(file_bytes, dpi=200, fmt="png")
    except Exception as e:
        logger.error(f"pdf2image conversion failed for {file_name}: {e}")
        return None

    segments: list[TextSegment] = []
    for page_num, image in enumerate(images, start=1):
        try:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            png_bytes = buf.getvalue()

            response = ocr_client.invoke(
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": "png",
                                "source": {"bytes": png_bytes},
                            }
                        },
                        {
                            "text": (
                                "Extract all text from this document page exactly "
                                "as it appears. Output only the extracted text, "
                                "no commentary."
                            )
                        },
                    ],
                }],
                max_tokens=2048,
                temperature=0.0,
            )
            text = response.get("content", "").strip()
            if text:
                segments.append(TextSegment(
                    text=text,
                    page_number=page_num,
                    section_title=None,
                ))
        except Exception as e:
            logger.warning(f"OCR failed for page {page_num} of {file_name}: {e}")
            continue

    if not segments:
        logger.warning(f"OCR produced no text for {file_name}")
        return None

    total_chars = sum(len(s.text) for s in segments)
    logger.info(
        f"OCR completed for '{file_name}': "
        f"{len(segments)}/{len(images)} pages extracted, {total_chars} chars total"
    )
    return segments


def _extract_pptx(file_bytes: bytes, file_name: str) -> list[TextSegment] | None:
    """
    Extract text from PPTX bytes using python-pptx.

    Returns one TextSegment per slide. The section_title is the first
    non-empty text shape on the slide (typically the title placeholder).
    """
    try:
        from pptx import Presentation
    except ImportError:
        logger.error("python-pptx is not installed. Run: pip install python-pptx")
        return None

    try:
        prs = Presentation(io.BytesIO(file_bytes))
        segments: list[TextSegment] = []

        for slide_num, slide in enumerate(prs.slides, start=1):
            parts = []
            first_text: str | None = None

            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            if first_text is None:
                                first_text = text
                            parts.append(text)
                elif shape.has_table:
                    for row in shape.table.rows:
                        cell_texts = [c.text.strip() for c in row.cells if c.text.strip()]
                        if cell_texts:
                            parts.append(" | ".join(cell_texts))

            if parts:
                segments.append(TextSegment(
                    text="\n".join(parts),
                    page_number=slide_num,
                    section_title=first_text,
                ))

        if not segments:
            logger.warning(f"No text extracted from PPTX: {file_name}")
            return None

        logger.info(
            f"PPTX extracted for '{file_name}': "
            f"{len(segments)}/{len(prs.slides)} slides with text"
        )
        return segments

    except Exception as e:
        logger.error(f"PPTX extraction failed for {file_name}: {e}")
        return None


def _extract_docx(file_bytes: bytes, file_name: str) -> list[TextSegment] | None:
    """
    Extract text from DOCX bytes using python-docx.

    Groups body paragraphs under the nearest preceding heading, yielding
    one TextSegment per heading section. Paragraphs before the first heading
    are grouped under a None section_title.
    """
    try:
        import docx
    except ImportError:
        logger.error("python-docx is not installed. Run: pip install python-docx")
        return None

    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        segments: list[TextSegment] = []
        current_heading: str | None = None
        current_paras: list[str] = []

        def _flush():
            if current_paras:
                segments.append(TextSegment(
                    text="\n\n".join(current_paras),
                    page_number=None,
                    section_title=current_heading,
                ))

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name if para.style else ""
            if style_name.startswith("Heading"):
                _flush()
                current_heading = text
                current_paras = []
            else:
                current_paras.append(text)

        _flush()

        if not segments:
            logger.warning(f"No text extracted from DOCX: {file_name}")
            return None

        return segments

    except Exception as e:
        logger.error(f"DOCX extraction failed for {file_name}: {e}")
        return None
