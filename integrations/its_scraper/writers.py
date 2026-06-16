
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

from markdownify import markdownify as html_to_markdown

from .config import OutputFormat, ScrapeConfig
from .types import Article

WriterFactory = Callable[[ScrapeConfig], "BaseWriter"]
_WRITER_REGISTRY: Dict[str, WriterFactory] = {}


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(article: Article, base_dir: Path) -> Path:
    target = base_dir / "article.json"
    _ensure_dir(target.parent)
    target.write_text(
        json.dumps(article.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def write_markdown(article: Article, base_dir: Path) -> Path:
    target = base_dir / "article.md"
    _ensure_dir(target.parent)
    md_body = html_to_markdown(article.content_html, heading_style="ATX")
    metadata = f"""---
title: "{article.title}"
source: "{article.url}"
fetched_at: "{article.fetched_at.isoformat()}"
tags: {article.tags}
breadcrumbs: {article.breadcrumbs}
---

"""
    target.write_text(metadata + md_body, encoding="utf-8")
    return target


def write_txt(article: Article, base_dir: Path) -> Path:
    target = base_dir / "article.txt"
    _ensure_dir(target.parent)
    target.write_text(
        f"{article.title}\n{'=' * len(article.title)}\n\n{article.content_text}\n",
        encoding="utf-8",
    )
    return target


def write_metadata(
    article: Article,
    base_dir: Path,
    config: ScrapeConfig,
    existing_meta: Optional[Dict[str, object]] = None,
) -> Path:
    target = base_dir / config.metadata_filename
    data = article.to_dict()
    if not config.rag_metadata:
        data.pop("breadcrumbs", None)
        data.pop("tags", None)
    if existing_meta and existing_meta.get("content_hash") != article.content_hash:
        data.setdefault("meta", {})
        data["meta"]["previous_version"] = existing_meta.get("fetched_at")
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def persist_article(
    article: Article,
    config: ScrapeConfig,
    *,
    existing_meta: Optional[Dict[str, object]] = None,
    external_writers: Optional[Iterable["BaseWriter"]] = None,
) -> Iterable[Path]:
    slug_source = article.meta.get("canonical") or article.url or article.title
    slug = slugify(slug_source)
    article_dir = Path(config.output_directory) / slug
    metadata_path = article_dir / config.metadata_filename

    if config.update_only and existing_meta:
        if existing_meta.get("content_hash") == article.content_hash:
            return []

    if metadata_path.exists() and not existing_meta:
        try:
            existing_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_meta = None

    if existing_meta and existing_meta.get("content_hash") != article.content_hash:
        version_stamp = str(existing_meta.get("fetched_at", "previous"))
        version_stamp = version_stamp.replace(":", "-")
        version_dir = article_dir / "versions" / version_stamp
        _ensure_dir(version_dir)
        for candidate in ["article.json", "article.md", "article.txt", config.metadata_filename]:
            src = article_dir / candidate
            if src.exists():
                shutil.move(str(src), version_dir / candidate)

    persisted = []
    for fmt in config.formats:
        if fmt == OutputFormat.json:
            persisted.append(write_json(article, article_dir))
        elif fmt == OutputFormat.markdown:
            persisted.append(write_markdown(article, article_dir))
        elif fmt == OutputFormat.txt:
            persisted.append(write_txt(article, article_dir))
    persisted.append(
        write_metadata(article, article_dir, config, existing_meta=existing_meta)
    )
    for writer in external_writers or []:
        writer.write(article)
    return persisted


def slugify(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {" ", "-", "_", "/", ":", ".", "?", "="}:
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    return slug or "article"


class BaseWriter:
    def write(self, article: Article) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


def register_writer(name: str, factory: WriterFactory) -> None:
    _WRITER_REGISTRY[name] = factory


def get_writer(name: str, config: ScrapeConfig) -> BaseWriter:
    if name not in _WRITER_REGISTRY:
        raise KeyError(f"Writer '{name}' is not registered")
    return _WRITER_REGISTRY[name](config)

