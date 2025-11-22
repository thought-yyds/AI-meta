"""Multi-format parsing tool implemented as a LangChain BaseTool."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Set, Type

from pydantic import BaseModel, Field

from .base import ContextAwareTool, ToolExecutionError


class FileParserInput(BaseModel):
    """Schema describing the expected arguments for the document parser tool."""

    path: str = Field(..., description="Path to the document to parse.")
    max_sections: Optional[int] = Field(
        None,
        description=(
            "Optional limit for slides (pptx) or pages (pdf/docx). "
            "For plain-text files, limits the number of blocks returned."
        ),
    )


class FileParserTool(ContextAwareTool):
    """Extract structured text content from various document formats."""

    name: str = "file_parser"
    description: str = (
        "Parse a supported document (pptx, pdf, docx, txt, md) and return structured text."
    )
    args_schema: ClassVar[Type[FileParserInput]] = FileParserInput

    _TEXT_EXTENSIONS: ClassVar[Set[str]] = {".txt", ".md", ".markdown"}

    def _run(self, path: str, max_sections: Optional[int] = None) -> str:
        working_dir = Path(self.context.working_dir or Path.cwd())
        file_path = (working_dir / path).resolve()

        if not file_path.exists():
            raise ToolExecutionError(f"File not found: {file_path}")
        if max_sections is not None and max_sections <= 0:
            raise ToolExecutionError("Parameter 'max_sections' must be a positive integer.")

        suffix = file_path.suffix.lower()
        if suffix == ".pptx":
            payload = self._parse_pptx(file_path, max_sections)
        elif suffix == ".pdf":
            payload = self._parse_pdf(file_path, max_sections)
        elif suffix == ".docx":
            payload = self._parse_docx(file_path, max_sections)
        elif suffix in self._TEXT_EXTENSIONS:
            payload = self._parse_text(file_path, max_sections)
        else:
            supported = ", ".join(sorted({".pptx", ".pdf", ".docx", *self._TEXT_EXTENSIONS}))
            raise ToolExecutionError(
                f"Unsupported file extension '{suffix}'. Supported extensions: {supported}."
            )

        return self._as_json({"file": str(file_path), **payload})

    def _parse_pptx(self, file_path: Path, max_sections: Optional[int]) -> Dict[str, object]:
        try:
            from pptx import Presentation  # type: ignore
        except ImportError as exc:  # noqa: BLE001
            raise ToolExecutionError(
                "Missing dependency 'python-pptx'. Install it with 'pip install python-pptx'."
            ) from exc

        try:
            presentation = Presentation(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to open presentation: {exc}") from exc

        slides_data = []
        for idx, slide in enumerate(presentation.slides, start=1):
            if max_sections is not None and idx > max_sections:
                break
            title = slide.shapes.title.text if slide.shapes.title else f"Slide {idx}"
            bullets: List[str] = []
            for shape in slide.shapes:
                if not getattr(shape, "has_text_frame", False):
                    continue
                text = shape.text_frame.text.strip()
                if text:
                    bullets.append(text)
            slides_data.append(
                {
                    "index": idx,
                    "title": title.strip(),
                    "content": bullets,
                }
            )

        return {"type": "pptx", "slide_count": len(slides_data), "slides": slides_data}

    def _parse_pdf(self, file_path: Path, max_sections: Optional[int]) -> Dict[str, object]:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError as exc:  # noqa: BLE001
            raise ToolExecutionError(
                "Missing dependency 'PyPDF2'. Install it with 'pip install PyPDF2'."
            ) from exc

        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to open PDF: {exc}") from exc

        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            if max_sections is not None and idx > max_sections:
                break
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                raise ToolExecutionError(f"Failed to extract text from page {idx}: {exc}") from exc
            pages.append({"index": idx, "content": text.strip()})

        return {"type": "pdf", "page_count": len(reader.pages), "pages": pages}

    def _parse_docx(self, file_path: Path, max_sections: Optional[int]) -> Dict[str, object]:
        try:
            from docx import Document  # type: ignore
        except ImportError as exc:  # noqa: BLE001
            raise ToolExecutionError(
                "Missing dependency 'python-docx'. Install it with 'pip install python-docx'."
            ) from exc

        try:
            document = Document(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to open DOCX: {exc}") from exc

        paragraphs: List[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if text:
                paragraphs.append(text)
            if max_sections is not None and len(paragraphs) >= max_sections:
                break

        return {"type": "docx", "paragraphs": paragraphs, "paragraph_count": len(document.paragraphs)}

    def _parse_text(self, file_path: Path, max_sections: Optional[int]) -> Dict[str, object]:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to read text file: {exc}") from exc

        lines = [line.strip() for line in content.splitlines()]
        if max_sections is not None:
            lines = lines[:max_sections]
        return {"type": "text", "lines": lines, "line_count": len(content.splitlines())}

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("FileParserTool does not support async execution.")

