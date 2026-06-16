"""
Docling Document Processor Integration

Provides advanced document intelligence for AI agents:
- PDF parsing with layout understanding
- Table extraction
- Formula recognition
- Multi-format support (DOCX, PPTX, XLSX, Audio)
- Reading order detection
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Supported document types"""
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    MARKDOWN = "md"
    AUDIO_WAV = "wav"
    AUDIO_MP3 = "mp3"
    IMAGE = "image"


class DoclingProcessor:
    """
    Docling-based document processor

    Features:
    - Advanced PDF understanding
    - Table structure extraction
    - Formula recognition
    - Audio transcription (ASR)
    - Multi-format support
    - Unified document representation
    """

    def __init__(self):
        """Initialize Docling processor"""
        self.logger = logging.getLogger("docling_processor")

        try:
            from docling.document_converter import DocumentConverter
            self.converter = DocumentConverter()
            self.logger.info("Docling processor initialized successfully")
        except ImportError as e:
            self.logger.error(f"Docling not installed: {e}")
            self.converter = None

    async def process_document(
        self,
        file_path: str,
        output_format: str = "markdown"
    ) -> Dict[str, Any]:
        """
        Process document with Docling

        Args:
            file_path: Path to document
            output_format: Output format (markdown, html, json)

        Returns:
            Processed document data
        """
        if not self.converter:
            return self._fallback_processing(file_path)

        try:
            # Convert document
            result = self.converter.convert(file_path)

            # Extract content based on format
            if output_format == "markdown":
                content = result.document.export_to_markdown()
            elif output_format == "html":
                content = result.document.export_to_html()
            else:  # json
                content = result.document.export_to_dict()

            # Extract metadata
            metadata = {
                "file_path": file_path,
                "file_type": self._detect_type(file_path),
                "pages": getattr(result.document, "num_pages", 0),
                "has_tables": self._has_tables(result.document),
                "has_formulas": self._has_formulas(result.document),
                "has_images": self._has_images(result.document)
            }

            # Extract structure
            structure = self._extract_structure(result.document)

            # Extract tables
            tables = self._extract_tables(result.document)

            # Extract formulas
            formulas = self._extract_formulas(result.document)

            self.logger.info(
                f"Processed document: {file_path}",
                extra={
                    "pages": metadata["pages"],
                    "tables": len(tables),
                    "formulas": len(formulas)
                }
            )

            return {
                "content": content,
                "metadata": metadata,
                "structure": structure,
                "tables": tables,
                "formulas": formulas,
                "status": "success"
            }

        except Exception as e:
            self.logger.error(f"Document processing failed: {e}")
            return {
                "content": "",
                "metadata": {"error": str(e)},
                "status": "error"
            }

    async def process_pdf(
        self,
        pdf_path: str
    ) -> Dict[str, Any]:
        """
        Process PDF with advanced features

        Args:
            pdf_path: Path to PDF

        Returns:
            Processed PDF data with layout understanding
        """
        return await self.process_document(pdf_path, "markdown")

    async def extract_tables(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Extract tables from document

        Args:
            file_path: Path to document

        Returns:
            List of extracted tables
        """
        result = await self.process_document(file_path, "json")
        return result.get("tables", [])

    async def transcribe_audio(
        self,
        audio_path: str
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using ASR

        Args:
            audio_path: Path to audio file (WAV, MP3)

        Returns:
            Transcription result
        """
        if not self.converter:
            return {"text": "", "status": "error", "error": "Docling not available"}

        try:
            result = self.converter.convert(audio_path)

            return {
                "text": result.document.export_to_markdown(),
                "duration": getattr(result.document, "duration", 0),
                "language": getattr(result.document, "language", "unknown"),
                "status": "success"
            }

        except Exception as e:
            self.logger.error(f"Audio transcription failed: {e}")
            return {
                "text": "",
                "status": "error",
                "error": str(e)
            }

    def _detect_type(self, file_path: str) -> str:
        """Detect document type from file extension"""
        ext = Path(file_path).suffix.lower().lstrip('.')

        type_map = {
            'pdf': DocumentType.PDF.value,
            'docx': DocumentType.DOCX.value,
            'pptx': DocumentType.PPTX.value,
            'xlsx': DocumentType.XLSX.value,
            'html': DocumentType.HTML.value,
            'md': DocumentType.MARKDOWN.value,
            'wav': DocumentType.AUDIO_WAV.value,
            'mp3': DocumentType.AUDIO_MP3.value,
            'png': DocumentType.IMAGE.value,
            'jpg': DocumentType.IMAGE.value,
            'jpeg': DocumentType.IMAGE.value
        }

        return type_map.get(ext, 'unknown')

    def _extract_structure(self, document) -> Dict[str, Any]:
        """Extract document structure"""
        try:
            return {
                "sections": getattr(document, "sections", []),
                "headings": getattr(document, "headings", []),
                "reading_order": getattr(document, "reading_order", [])
            }
        except:
            return {}

    def _extract_tables(self, document) -> List[Dict[str, Any]]:
        """Extract tables from document"""
        try:
            tables = getattr(document, "tables", [])
            return [
                {
                    "index": i,
                    "rows": len(table.get("rows", [])),
                    "columns": len(table.get("columns", [])),
                    "data": table.get("data", [])
                }
                for i, table in enumerate(tables)
            ]
        except:
            return []

    def _extract_formulas(self, document) -> List[str]:
        """Extract formulas from document"""
        try:
            return getattr(document, "formulas", [])
        except:
            return []

    def _has_tables(self, document) -> bool:
        """Check if document has tables"""
        try:
            return len(getattr(document, "tables", [])) > 0
        except:
            return False

    def _has_formulas(self, document) -> bool:
        """Check if document has formulas"""
        try:
            return len(getattr(document, "formulas", [])) > 0
        except:
            return False

    def _has_images(self, document) -> bool:
        """Check if document has images"""
        try:
            return len(getattr(document, "images", [])) > 0
        except:
            return False

    def _fallback_processing(self, file_path: str) -> Dict[str, Any]:
        """Fallback processing when Docling is not available"""
        self.logger.warning("Using fallback processing (Docling not available)")

        # Try basic text extraction
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return {
                "content": content,
                "metadata": {
                    "file_path": file_path,
                    "processing": "fallback"
                },
                "status": "success"
            }
        except:
            return {
                "content": "",
                "metadata": {"error": "Fallback processing failed"},
                "status": "error"
            }


# Singleton instance
_docling_processor: Optional[DoclingProcessor] = None


def get_docling_processor() -> DoclingProcessor:
    """
    Get or create Docling processor singleton

    Returns:
        DoclingProcessor instance
    """
    global _docling_processor

    if _docling_processor is None:
        _docling_processor = DoclingProcessor()

    return _docling_processor


__all__ = [
    "DoclingProcessor",
    "DocumentType",
    "get_docling_processor"
]
