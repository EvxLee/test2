"""
Tests for the embedding pipeline refactor:
  - chat.embed_documents  (_estimate_tokens, chunk_text, fetch_files,
                           _upsert_document, embed_and_store, _store_batch)
  - chat.file_extractor   (extract_text returning TextSegment values)
  - chat.tools            (semantic_search against the new schema)
"""

import json
import sys
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


def _segment(text: str, page_number: int | None = None, section_title: str | None = None):
    from chat.file_extractor import TextSegment
    return TextSegment(text=text, page_number=page_number, section_title=section_title)


class TestEstimateTokens:
    def _fn(self):
        from chat.embed_documents import _estimate_tokens
        return _estimate_tokens

    def test_returns_len_divided_by_four(self):
        assert self._fn()("a" * 400) == 100

    def test_empty_string(self):
        assert self._fn()("") == 0


class TestChunkText:
    def _fn(self):
        from chat.embed_documents import chunk_text
        return chunk_text

    def test_short_text_returned_as_single_chunk(self):
        result = self._fn()("Hello world", chunk_size=1000)
        assert result == ["Hello world"]

    def test_empty_string_returns_empty_list(self):
        assert self._fn()("") == []

    def test_none_returns_empty_list(self):
        assert self._fn()(None) == []

    def test_long_flat_text_splits_into_multiple_chunks(self):
        text = "a" * 3000
        chunks = self._fn()(text, chunk_size=1000, overlap=0)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_paragraph_boundary_respected(self):
        para1 = "First paragraph. " * 60
        para2 = "Second paragraph. " * 60
        text = para1.strip() + "\n\n" + para2.strip()
        chunks = self._fn()(text, chunk_size=1000, overlap=0)
        assert not any(
            "First paragraph" in chunk and "Second paragraph" in chunk
            for chunk in chunks
        )

    def test_short_paragraphs_merged_up_to_chunk_size(self):
        paras = ["word " * 20 for _ in range(5)]
        text = "\n\n".join(paras)
        chunks = self._fn()(text, chunk_size=1500, overlap=0)
        assert len(chunks) == 1

    def test_overlap_shared_between_adjacent_chunks(self):
        text = "x" * 3000
        chunks = self._fn()(text, chunk_size=1000, overlap=200)
        assert len(chunks) > 1
        assert chunks[0][-200:] == chunks[1][:200]

    def test_sentence_boundary_preference(self):
        sentence = "word " * 140 + ". " + "tail " * 200
        chunks = self._fn()(sentence, chunk_size=1000, overlap=0)
        assert chunks[0].endswith(".")

    def test_filters_empty_chunks(self):
        chunks = self._fn()("short text", chunk_size=100, overlap=50)
        assert all(chunk.strip() for chunk in chunks)

    def test_token_guard_force_splits_oversized_chunk(self):
        from chat.embed_documents import _MAX_SAFE_TOKENS, _estimate_tokens

        oversized = "a" * ((_MAX_SAFE_TOKENS + 1) * 4)
        chunks = self._fn()(oversized, chunk_size=len(oversized), overlap=0)
        assert all(_estimate_tokens(chunk) <= _MAX_SAFE_TOKENS for chunk in chunks)


class TestExtractText:
    def _fn(self):
        from chat.file_extractor import extract_text
        return extract_text

    def _paragraph(self, text: str, style_name: str = "Normal"):
        para = MagicMock()
        para.text = text
        para.style = MagicMock()
        para.style.name = style_name
        return para

    def test_unsupported_extension_returns_none(self):
        assert self._fn()(b"data", "report.xlsx") is None

    def test_pdf_with_text_returns_segments_with_page_numbers(self):
        extract_text = self._fn()

        fake_page1 = MagicMock()
        fake_page1.extract_text.return_value = "This is the full text of page one of the document."
        fake_page2 = MagicMock()
        fake_page2.extract_text.return_value = "This is the full text of page two of the document."

        fake_pdf = MagicMock()
        fake_pdf.__enter__.return_value = fake_pdf
        fake_pdf.__exit__.return_value = False
        fake_pdf.pages = [fake_page1, fake_page2]

        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open.return_value = fake_pdf

        with patch.dict(sys.modules, {"pdfplumber": fake_pdfplumber}):
            result = extract_text(b"pdf-bytes", "doc.pdf")

        assert result == [
            _segment(
                "This is the full text of page one of the document.",
                page_number=1,
            ),
            _segment(
                "This is the full text of page two of the document.",
                page_number=2,
            ),
        ]

    def test_pdf_exception_returns_none(self):
        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open.side_effect = Exception("corrupt")
        with patch.dict(sys.modules, {"pdfplumber": fake_pdfplumber}):
            assert self._fn()(b"bad", "bad.pdf") is None

    def _make_sparse_pdf_mocks(self):
        fake_page = MagicMock()
        fake_page.extract_text.return_value = "Hi"

        fake_pdf = MagicMock()
        fake_pdf.__enter__.return_value = fake_pdf
        fake_pdf.__exit__.return_value = False
        fake_pdf.pages = [fake_page]

        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open.return_value = fake_pdf
        return fake_pdfplumber

    def test_sparse_pdf_falls_back_to_ocr(self):
        extract_text = self._fn()
        fake_pdfplumber = self._make_sparse_pdf_mocks()

        fake_image = MagicMock()
        fake_image.save = MagicMock()
        fake_pdf2image = MagicMock()
        fake_pdf2image.convert_from_bytes.return_value = [fake_image]

        mock_ocr_client = MagicMock()
        mock_ocr_client.invoke.return_value = {"content": "OCR extracted text from page"}

        with patch.dict(sys.modules, {
            "pdfplumber": fake_pdfplumber,
            "pdf2image": fake_pdf2image,
        }):
            with patch("chat.file_extractor.BedrockLLMClient", return_value=mock_ocr_client):
                result = extract_text(b"scanned-pdf-bytes", "scan.pdf")

        assert result == [_segment("OCR extracted text from page", page_number=1)]
        mock_ocr_client.invoke.assert_called_once()

    def test_ocr_invoke_sends_image_content_block(self):
        extract_text = self._fn()
        fake_pdfplumber = self._make_sparse_pdf_mocks()

        fake_image = MagicMock()
        fake_image.save = MagicMock()
        fake_pdf2image = MagicMock()
        fake_pdf2image.convert_from_bytes.return_value = [fake_image]

        mock_ocr_client = MagicMock()
        mock_ocr_client.invoke.return_value = {"content": "text"}

        with patch.dict(sys.modules, {
            "pdfplumber": fake_pdfplumber,
            "pdf2image": fake_pdf2image,
        }):
            with patch("chat.file_extractor.BedrockLLMClient", return_value=mock_ocr_client):
                extract_text(b"bytes", "scan.pdf")

        call_kwargs = mock_ocr_client.invoke.call_args
        messages = call_kwargs.kwargs.get("messages") if call_kwargs.kwargs else call_kwargs.args[0]
        content_blocks = messages[0]["content"]

        block_types = [list(block.keys())[0] for block in content_blocks]
        assert "image" in block_types
        assert "text" in block_types

    def test_ocr_model_can_be_overridden_by_env(self):
        extract_text = self._fn()
        fake_pdfplumber = self._make_sparse_pdf_mocks()

        fake_image = MagicMock()
        fake_image.save = MagicMock()
        fake_pdf2image = MagicMock()
        fake_pdf2image.convert_from_bytes.return_value = [fake_image]

        mock_ocr_client = MagicMock()
        mock_ocr_client.invoke.return_value = {"content": "text"}

        with patch.dict(sys.modules, {
            "pdfplumber": fake_pdfplumber,
            "pdf2image": fake_pdf2image,
        }):
            with patch.dict("os.environ", {"BEDROCK_OCR_MODEL_ID": "custom.model"}):
                with patch("chat.file_extractor.BedrockLLMClient", return_value=mock_ocr_client) as mock_ctor:
                    extract_text(b"bytes", "scan.pdf")

        assert mock_ctor.call_args.kwargs["model_id"] == "custom.model"

    def test_ocr_skips_page_on_error_continues(self):
        extract_text = self._fn()
        fake_pdfplumber = self._make_sparse_pdf_mocks()
        fake_pdfplumber.open.return_value.__enter__.return_value.pages = [
            MagicMock(extract_text=MagicMock(return_value="x")),
            MagicMock(extract_text=MagicMock(return_value="x")),
        ]
        fake_pdfplumber.open.return_value.__exit__.return_value = False

        fake_pdf2image = MagicMock()
        fake_pdf2image.convert_from_bytes.return_value = [MagicMock(), MagicMock()]

        mock_ocr_client = MagicMock()
        mock_ocr_client.invoke.side_effect = [
            Exception("page 1 failed"),
            {"content": "page 2 text"},
        ]

        with patch.dict(sys.modules, {
            "pdfplumber": fake_pdfplumber,
            "pdf2image": fake_pdf2image,
        }):
            with patch("chat.file_extractor.BedrockLLMClient", return_value=mock_ocr_client):
                result = extract_text(b"bytes", "scan.pdf")

        assert result == [_segment("page 2 text", page_number=2)]

    def test_pdf_no_text_and_ocr_returns_none(self):
        extract_text = self._fn()

        fake_page = MagicMock()
        fake_page.extract_text.return_value = None
        fake_pdf = MagicMock()
        fake_pdf.__enter__.return_value = fake_pdf
        fake_pdf.__exit__.return_value = False
        fake_pdf.pages = [fake_page]
        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open.return_value = fake_pdf

        with patch.dict(sys.modules, {"pdfplumber": fake_pdfplumber}):
            with patch("chat.file_extractor._extract_pdf_ocr", return_value=None):
                result = extract_text(b"bytes", "scan.pdf")

        assert result is None

    def test_docx_groups_body_paragraphs_without_heading(self):
        extract_text = self._fn()

        fake_doc = MagicMock()
        fake_doc.paragraphs = [
            self._paragraph("First paragraph"),
            self._paragraph("   "),
            self._paragraph("Second paragraph"),
        ]

        fake_docx = MagicMock()
        fake_docx.Document.return_value = fake_doc

        with patch.dict(sys.modules, {"docx": fake_docx}):
            result = extract_text(b"docx-bytes", "notes.docx")

        assert result == [
            _segment("First paragraph\n\nSecond paragraph")
        ]

    def test_docx_groups_paragraphs_under_heading(self):
        extract_text = self._fn()

        fake_doc = MagicMock()
        fake_doc.paragraphs = [
            self._paragraph("Executive Summary", style_name="Heading 1"),
            self._paragraph("Summary paragraph one."),
            self._paragraph("Summary paragraph two."),
            self._paragraph("Details", style_name="Heading 2"),
            self._paragraph("Detailed paragraph."),
        ]

        fake_docx = MagicMock()
        fake_docx.Document.return_value = fake_doc

        with patch.dict(sys.modules, {"docx": fake_docx}):
            result = extract_text(b"docx-bytes", "notes.docx")

        assert result == [
            _segment(
                "Summary paragraph one.\n\nSummary paragraph two.",
                section_title="Executive Summary",
            ),
            _segment("Detailed paragraph.", section_title="Details"),
        ]

    def test_docx_all_empty_paragraphs_returns_none(self):
        fake_doc = MagicMock()
        fake_doc.paragraphs = []
        fake_docx = MagicMock()
        fake_docx.Document.return_value = fake_doc

        with patch.dict(sys.modules, {"docx": fake_docx}):
            assert self._fn()(b"bytes", "empty.docx") is None

    def test_docx_exception_returns_none(self):
        fake_docx = MagicMock()
        fake_docx.Document.side_effect = Exception("corrupt")

        with patch.dict(sys.modules, {"docx": fake_docx}):
            assert self._fn()(b"bad", "bad.docx") is None

class TestFetchFiles:
    def _fn(self):
        from chat.embed_documents import fetch_files
        return fetch_files

    def _fake_row(
        self,
        file_id="101",
        file_name="report.pdf",
        spaces_key="monday/101/report.pdf",
        category="Legal",
        owner="Alice",
    ):
        return {
            "id": file_id,
            "fileName": file_name,
            "spacesKey": spaces_key,
            "category": category,
            "owner": owner,
        }

    def test_happy_path_yields_correct_document(self):
        row = self._fake_row()
        segments = [
            _segment("Page one text", page_number=1),
            _segment("Page two text", page_number=2),
        ]

        with patch("chat.embed_documents.fetch_all", return_value=[row]):
            with patch("files.spaces.download", return_value=b"bytes"):
                with patch("chat.embed_documents.extract_text", return_value=segments):
                    results = list(self._fn()())

        assert len(results) == 1
        doc = results[0]
        assert doc["source_type"] == "file"
        assert doc["source_table"] == "monday.files"
        assert doc["content"] == "Page one text\n\nPage two text"
        assert doc["segments"] == segments
        assert doc["metadata"]["file_name"] == "report.pdf"
        assert doc["metadata"]["spaces_key"] == "monday/101/report.pdf"
        assert doc["metadata"]["category"] == "Legal"

    def test_board_id_override_used_in_query(self):
        with patch("chat.embed_documents.fetch_all", return_value=[]) as mock_fetch:
            list(self._fn()(board_id="custom-board"))

        _sql, params = mock_fetch.call_args.args
        assert list(params) == ["custom-board"]

    def test_source_id_is_deterministic_uuid5(self):
        row = self._fake_row(file_id="42")
        expected_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "42"))

        with patch("chat.embed_documents.fetch_all", return_value=[row]):
            with patch("files.spaces.download", return_value=b"bytes"):
                with patch("chat.embed_documents.extract_text", return_value=[_segment("text")]):
                    results = list(self._fn()())

        assert results[0]["source_id"] == expected_id

    def test_skips_row_when_download_fails(self):
        rows = [
            self._fake_row(file_id="1"),
            self._fake_row(file_id="2", file_name="ok.pdf", spaces_key="monday/2/ok.pdf"),
        ]

        with patch("chat.embed_documents.fetch_all", return_value=rows):
            with patch("files.spaces.download", side_effect=[Exception("network error"), b"bytes"]):
                with patch("chat.embed_documents.extract_text", return_value=[_segment("text")]):
                    results = list(self._fn()())

        assert len(results) == 1
        assert results[0]["metadata"]["file_name"] == "ok.pdf"

    def test_skips_row_when_extract_text_returns_none(self):
        rows = [
            self._fake_row(file_id="1", file_name="image.pdf"),
            self._fake_row(file_id="2", file_name="real.pdf", spaces_key="monday/2/real.pdf"),
        ]

        with patch("chat.embed_documents.fetch_all", return_value=rows):
            with patch("files.spaces.download", return_value=b"bytes"):
                with patch("chat.embed_documents.extract_text", side_effect=[None, [_segment("good text")]]):
                    results = list(self._fn()())

        assert len(results) == 1
        assert results[0]["metadata"]["file_name"] == "real.pdf"

    def test_skips_row_when_file_exceeds_size_limit(self):
        row = self._fake_row()

        with patch("chat.embed_documents.fetch_all", return_value=[row]):
            with patch("files.spaces.download", return_value=b"x" * 11):
                with patch("chat.embed_documents.extract_text") as mock_extract:
                    results = list(self._fn()(max_file_bytes=10))

        assert results == []
        mock_extract.assert_not_called()


class TestUpsertDocument:
    def _fn(self):
        from chat.embed_documents import _upsert_document
        return _upsert_document

    def test_executes_document_upsert_and_returns_id(self):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = ["doc-uuid"]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_conn.cursor.return_value.__exit__.return_value = False

        @contextmanager
        def fake_get_conn():
            yield mock_conn

        doc = {
            "source_type": "file",
            "source_id": str(uuid.uuid4()),
            "source_table": "monday.files",
            "metadata": {
                "file_name": "report.pdf",
                "spaces_key": "monday/123/report.pdf",
                "category": "Legal",
                "owner": "Alice",
            },
        }

        with patch("chat.embed_documents.get_conn", fake_get_conn):
            result = self._fn()(doc)

        assert result == "doc-uuid"
        sql, params = mock_cur.execute.call_args.args
        assert "INSERT INTO llm.documents" in sql
        assert "ON CONFLICT (source_type, source_id) DO UPDATE" in sql
        assert params[0] == "file"
        assert params[2] == "monday.files"
        assert params[3] == "report.pdf"
        assert params[4] == "monday/123/report.pdf"
        assert params[7] == "pdf"                          # file_type derived from extension
        assert json.loads(params[8])["owner"] == "Alice"  # metadata JSON shifted to index 8


class TestEmbedAndStore:
    def _fn(self):
        from chat.embed_documents import embed_and_store
        return embed_and_store

    def _make_doc(
        self,
        content="Some text content",
        category="Legal",
        file_name="f.pdf",
        segments=None,
    ):
        segments = segments or [_segment(content)]
        return {
            "source_type": "file",
            "source_id": str(uuid.uuid4()),
            "source_table": "monday.files",
            "content": content,
            "segments": segments,
            "metadata": {
                "file_name": file_name,
                "category": category,
                "spaces_key": f"monday/test/{file_name}",
                "owner": "Alice",
            },
        }

    def test_dry_run_does_not_call_store(self):
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.1] * 1024

        with patch("chat.embed_documents._store_batch") as mock_store:
            stats = self._fn()(iter([self._make_doc()]), embedding_client, dry_run=True)

        mock_store.assert_not_called()
        assert stats["errors"] == 0

    def test_calls_embed_per_chunk(self):
        text = "sentence. " * 200
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024

        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch"):
                stats = self._fn()(
                    iter([self._make_doc(content=text, segments=[_segment(text)])]),
                    embedding_client,
                    batch_size=100,
                    dry_run=False,
                )

        assert embedding_client.embed.call_count >= 2
        assert stats["errors"] == 0

    def test_batch_flushed_when_full(self):
        docs = [self._make_doc(f"Short doc {i}") for i in range(5)]
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024

        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch") as mock_store:
                self._fn()(iter(docs), embedding_client, batch_size=2, dry_run=False)

        assert mock_store.call_count >= 2

    def test_remaining_partial_batch_flushed(self):
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024

        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch") as mock_store:
                stats = self._fn()(
                    iter([self._make_doc("Short")]),
                    embedding_client,
                    batch_size=10,
                    dry_run=False,
                )

        mock_store.assert_called_once()
        assert stats["processed"] == 1

    def test_embedding_error_increments_errors(self):
        embedding_client = MagicMock()
        embedding_client.embed.side_effect = Exception("Bedrock unavailable")

        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch"):
                stats = self._fn()(iter([self._make_doc()]), embedding_client, dry_run=False)

        assert stats["errors"] > 0

    def test_metadata_header_prepended_to_embed_text_not_stored_chunk_text(self):
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024

        stored_items = []

        def capture_store(batch):
            stored_items.extend(batch)

        doc = self._make_doc(content="clause text", category="Contract", file_name="c.pdf")

        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch", side_effect=capture_store):
                self._fn()(iter([doc]), embedding_client, batch_size=50, dry_run=False)

        assert all(
            "[Category: Contract | File: c.pdf]" in call.args[0]
            for call in embedding_client.embed.call_args_list
        )
        assert all(not item["chunk_text"].startswith("[") for item in stored_items)

    def test_no_header_when_metadata_missing(self):
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024

        doc = {
            "source_type": "project",
            "source_id": str(uuid.uuid4()),
            "source_table": "master_dashboard.projects",
            "content": "project description text",
            "segments": [_segment("project description text")],
            "metadata": {},
        }

        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch"):
                self._fn()(iter([doc]), embedding_client, batch_size=50, dry_run=False)

        assert all(not call.args[0].startswith("[") for call in embedding_client.embed.call_args_list)

    def test_concurrent_embedding_uses_thread_pool(self):
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024
        docs = [
            self._make_doc(content="paragraph. " * 500, segments=[_segment("paragraph. " * 500)]),
            self._make_doc(content="more paragraph. " * 500, segments=[_segment("more paragraph. " * 500)]),
        ]

        pool_used = []
        original_executor = __import__(
            "concurrent.futures", fromlist=["ThreadPoolExecutor"]
        ).ThreadPoolExecutor

        class CapturingExecutor(original_executor):
            def __init__(self, *args, **kwargs):
                pool_used.append(True)
                super().__init__(*args, **kwargs)

        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents.ThreadPoolExecutor", CapturingExecutor):
                with patch("chat.embed_documents._store_batch"):
                    self._fn()(iter(docs), embedding_client, dry_run=False)

        assert pool_used == [True], "ThreadPoolExecutor should be instantiated once per run"

    def test_chunks_stored_in_original_order(self):
        embedding_client = MagicMock()
        call_counter = {"n": 0}

        def ordered_embed(_text):
            n = call_counter["n"]
            call_counter["n"] += 1
            vec = [0.0] * 1024
            vec[0] = float(n)
            return vec

        embedding_client.embed.side_effect = ordered_embed

        para_a = "Alpha sentence. " * 100
        para_b = "Beta sentence. " * 100
        para_c = "Gamma sentence. " * 100
        content = para_a.strip() + "\n\n" + para_b.strip() + "\n\n" + para_c.strip()
        doc = self._make_doc(content=content, segments=[_segment(content)])

        stored = []
        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch", side_effect=lambda batch: stored.extend(batch)):
                self._fn()(iter([doc]), embedding_client, batch_size=100, dry_run=False)

        contents = [item["chunk_text"] for item in stored]
        alpha_idx = next(i for i, chunk in enumerate(contents) if "Alpha" in chunk)
        beta_idx = next(i for i, chunk in enumerate(contents) if "Beta" in chunk)
        gamma_idx = next(i for i, chunk in enumerate(contents) if "Gamma" in chunk)
        assert alpha_idx < beta_idx < gamma_idx

    def test_segment_metadata_carried_to_stored_chunks(self):
        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024

        segments = [
            _segment("Introduction text", page_number=1, section_title="Intro"),
            _segment("Appendix text", page_number=8, section_title="Appendix"),
        ]
        doc = self._make_doc(
            content="Introduction text\n\nAppendix text",
            file_name="deck.pdf",
            segments=segments,
        )

        stored_items = []
        with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
            with patch("chat.embed_documents._store_batch", side_effect=lambda batch: stored_items.extend(batch)):
                self._fn()(iter([doc]), embedding_client, batch_size=50, dry_run=False)

        assert stored_items[0]["page_number"] == 1
        assert stored_items[0]["section_title"] == "Intro"
        assert stored_items[1]["page_number"] == 8
        assert stored_items[1]["section_title"] == "Appendix"


class TestStoreBatch:
    def _fn(self):
        from chat.embed_documents import _store_batch
        return _store_batch

    def test_executes_insert_with_correct_params(self):
        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_conn.cursor.return_value.__exit__.return_value = False

        @contextmanager
        def fake_get_conn():
            yield mock_conn

        item = {
            "document_id": "doc-uuid",
            "chunk_text": "chunk text",
            "page_number": 4,
            "section_title": "Executive Summary",
            "metadata": json.dumps({"file_name": "f.pdf"}),
            "embedding": [0.1, 0.2, 0.3],
        }

        with patch("chat.embed_documents.get_conn", fake_get_conn):
            self._fn()([item])

        sql, params = mock_cur.execute.call_args.args
        assert "INSERT INTO llm.document_chunks" in sql
        assert "ON CONFLICT (document_id, (md5(chunk_text)))" in sql
        assert params[0] == "doc-uuid"
        assert params[1] == "chunk text"
        assert params[2] == 4
        assert params[3] == "Executive Summary"
        assert params[5] == "[0.1,0.2,0.3]"

    def test_embedding_formatted_as_vector_string(self):
        captured = {}
        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_conn.cursor.return_value.__exit__.return_value = False
        mock_cur.execute.side_effect = lambda _sql, params: captured.update({"vec": params[5]})

        @contextmanager
        def fake_get_conn():
            yield mock_conn

        item = {
            "document_id": "doc-uuid",
            "chunk_text": "chunk text",
            "page_number": None,
            "section_title": None,
            "metadata": "{}",
            "embedding": [1.0, -2.5, 0.0],
        }

        with patch("chat.embed_documents.get_conn", fake_get_conn):
            self._fn()([item])

        assert captured["vec"] == "[1.0,-2.5,0.0]"


class TestFileEmbeddingEndToEnd:
    def test_two_files_produce_chunks_with_correct_metadata(self):
        from chat.embed_documents import embed_and_store, fetch_files

        rows = [
            {
                "id": "file-a",
                "fileName": "contract.pdf",
                "spacesKey": "monday/file-a/contract.pdf",
                "category": "Contract",
                "owner": "Alice",
            },
            {
                "id": "file-b",
                "fileName": "proposal.docx",
                "spacesKey": "monday/file-b/proposal.docx",
                "category": "Proposal",
                "owner": "Bob",
            },
        ]

        fake_segments = {
            "contract.pdf": [_segment("Contract clause text. " * 10, page_number=3)],
            "proposal.docx": [_segment("Proposal section text. " * 10, section_title="Overview")],
        }

        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024
        stored_items = []

        with patch("chat.embed_documents.fetch_all", return_value=rows):
            with patch("files.spaces.download", return_value=b"irrelevant-bytes"):
                with patch(
                    "chat.embed_documents.extract_text",
                    side_effect=lambda _file_bytes, file_name: fake_segments[file_name],
                ):
                    with patch("chat.embed_documents._upsert_document", side_effect=["doc-a", "doc-b"]):
                        with patch(
                            "chat.embed_documents._store_batch",
                            side_effect=lambda batch: stored_items.extend(batch),
                        ):
                            stats = embed_and_store(
                                fetch_files(),
                                embedding_client,
                                batch_size=50,
                                dry_run=False,
                            )

        assert stats["errors"] == 0
        assert stats["processed"] >= 2
        assert {item["document_id"] for item in stored_items} == {"doc-a", "doc-b"}

        file_names = {json.loads(item["metadata"])["file_name"] for item in stored_items}
        assert file_names == {"contract.pdf", "proposal.docx"}

        for item in stored_items:
            meta = json.loads(item["metadata"])
            assert "file_name" in meta
            assert "spaces_key" in meta
            assert "category" in meta
            assert "owner" in meta
            assert len(item["embedding"]) == 1024
            assert not item["chunk_text"].startswith("[")

        contract_item = next(item for item in stored_items if json.loads(item["metadata"])["file_name"] == "contract.pdf")
        proposal_item = next(item for item in stored_items if json.loads(item["metadata"])["file_name"] == "proposal.docx")
        assert contract_item["page_number"] == 3
        assert contract_item["section_title"] is None
        assert proposal_item["page_number"] is None
        assert proposal_item["section_title"] == "Overview"

    def test_embed_called_with_metadata_header(self):
        from chat.embed_documents import embed_and_store, fetch_files

        rows = [{
            "id": "x1",
            "fileName": "termsheet.pdf",
            "spacesKey": "monday/x1/termsheet.pdf",
            "category": "Legal",
            "owner": "Carol",
        }]

        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.0] * 1024

        with patch("chat.embed_documents.fetch_all", return_value=rows):
            with patch("files.spaces.download", return_value=b"bytes"):
                with patch(
                    "chat.embed_documents.extract_text",
                    return_value=[_segment("Term sheet clause. " * 5, page_number=1)],
                ):
                    with patch("chat.embed_documents._upsert_document", return_value="doc-1"):
                        with patch("chat.embed_documents._store_batch"):
                            embed_and_store(fetch_files(), embedding_client, dry_run=False)

        all_embed_texts = [call.args[0] for call in embedding_client.embed.call_args_list]
        assert all(
            "[Category: Legal | File: termsheet.pdf]" in text
            for text in all_embed_texts
        )


class TestSemanticSearch:
    def test_returns_chunk_text_page_and_section_from_new_schema(self):
        from chat.tools import RAGTools

        embedding_client = MagicMock()
        embedding_client.embed.return_value = [0.1] * 1024

        rows = [{
            "id": "chunk-1",
            "document_id": "doc-1",
            "source_type": "file",
            "source_id": str(uuid.uuid4()),
            "chunk_text": "Executive summary chunk",
            "page_number": 4,
            "section_title": "Executive Summary",
            "metadata": {"file_name": "deck.pdf"},
            "similarity": 0.9876,
        }]

        with patch("chat.tools.fetch_all", return_value=rows) as mock_fetch:
            result = RAGTools(embedding_client=embedding_client).semantic_search(
                query="executive summary",
                source_type="file",
                limit=3,
            )

        sql, params = mock_fetch.call_args.args
        assert "dc.chunk_text" in sql
        assert "JOIN llm.documents d ON d.id = dc.document_id" in sql
        assert "d.source_type = %s" in sql
        assert params[-1] == 3

        assert result.artifacts[0]["chunk_text"] == "Executive summary chunk"
        assert result.artifacts[0]["page_number"] == 4
        assert result.artifacts[0]["section_title"] == "Executive Summary"
        assert "Executive summary chunk" in result.content
        assert "page 4" in result.content
        assert "section Executive Summary" in result.content
