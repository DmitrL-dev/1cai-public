
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Article:
    url: str
    title: str
    content_html: str
    content_text: str
    fetched_at: datetime
    content_hash: str
    word_count: int
    excerpt: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    breadcrumbs: List[str] = field(default_factory=list)
    meta: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        base: Dict[str, object] = {
            "url": self.url,
            "title": self.title,
            "content_html": self.content_html,
            "content_text": self.content_text,
            "fetched_at": self.fetched_at.isoformat(),
            "content_hash": self.content_hash,
            "word_count": self.word_count,
            "excerpt": self.excerpt,
            "tags": self.tags,
            "breadcrumbs": self.breadcrumbs,
            "meta": self.meta,
        }
        return base

