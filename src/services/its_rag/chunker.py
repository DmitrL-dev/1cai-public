"""ITS Documentation Chunker — splits scraped text into embeddable chunks."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ITSChunk:
    """A chunk of ITS documentation ready for embedding."""

    text: str
    source_file: str
    section_title: str
    chunk_index: int
    its_article_id: str = ""
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


class ITSChunker:
    """Splits ITS documentation files into overlapping chunks for RAG indexing."""

    SECTION_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)+\.?\s+.+)$", re.MULTILINE)
    DEFAULT_CHUNK_SIZE = 4000  # ~1000 tokens
    DEFAULT_OVERLAP = 400  # ~100 tokens overlap

    def __init__(
        self,
        docs_dir: str = "docs/its_forms/sections",
        manifest_path: str = "docs/its_forms/manifest.json",
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ):
        self.docs_dir = Path(docs_dir)
        self.manifest_path = Path(manifest_path)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._manifest: Optional[dict] = None

    @property
    def manifest(self) -> dict:
        """Load and cache manifest."""
        if self._manifest is None:
            if self.manifest_path.exists():
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    self._manifest = json.load(f)
            else:
                self._manifest = {}
        return self._manifest

    def _get_article_id(self, filename: str) -> str:
        """Extract ITS article ID from manifest by filename."""
        for entry in self.manifest.get("chapter7", []):
            if entry.get("file", "").endswith(filename) or filename in entry.get(
                "file", ""
            ):
                return entry.get("ti", "")
        # Try extracting from filename pattern: ch7_001_TI000001468_...
        match = re.search(r"(TI\d+)", filename)
        return match.group(1) if match else ""

    def _split_into_sections(self, text: str) -> List[tuple]:
        """Split text into (title, content) sections by headings."""
        matches = list(self.SECTION_HEADING_RE.finditer(text))
        if not matches:
            return [("untitled", text)]

        sections = []
        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if content:
                sections.append((title, content))
        return sections

    def _chunk_text(self, text: str, base_meta: dict) -> List[ITSChunk]:
        """Split text into overlapping chunks."""
        if len(text) <= self.chunk_size:
            return [
                ITSChunk(
                    text=text.strip(),
                    chunk_index=0,
                    **base_meta,
                )
            ]

        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = start + self.chunk_size
            # Try to break at paragraph boundary
            if end < len(text):
                para_break = text.rfind("\n\n", start + self.chunk_size // 2, end + 200)
                if para_break > start:
                    end = para_break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    ITSChunk(
                        text=chunk_text,
                        chunk_index=idx,
                        **base_meta,
                    )
                )
                idx += 1

            start = end - self.overlap
            if start >= len(text):
                break

        return chunks

    def chunk_file(self, filepath: Path) -> List[ITSChunk]:
        """Process a single file into chunks."""
        text = filepath.read_text(encoding="utf-8")
        if not text.strip():
            return []

        article_id = self._get_article_id(filepath.name)
        sections = self._split_into_sections(text)

        all_chunks = []
        for title, content in sections:
            base = {
                "source_file": filepath.name,
                "section_title": title,
                "its_article_id": article_id,
            }
            all_chunks.extend(self._chunk_text(content, base))

        return all_chunks

    def chunk_all(self) -> List[ITSChunk]:
        """Process all ITS documentation files."""
        if not self.docs_dir.exists():
            raise FileNotFoundError(f"ITS docs directory not found: {self.docs_dir}")

        all_chunks = []
        files = sorted(self.docs_dir.glob("*.txt"))
        for filepath in files:
            chunks = self.chunk_file(filepath)
            all_chunks.extend(chunks)

        return all_chunks
