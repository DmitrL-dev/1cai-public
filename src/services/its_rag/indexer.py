"""ITS Documentation Indexer — embeds chunks and stores in Qdrant."""

import hashlib
import logging
from typing import List, Optional

from .chunker import ITSChunk, ITSChunker

logger = logging.getLogger(__name__)


class ITSIndexer:
    """Indexes ITS documentation chunks into Qdrant for semantic search.

    Usage:
        indexer = ITSIndexer()
        stats = await indexer.index_all()
        print(f"Indexed {stats['chunks_indexed']} chunks")
    """

    COLLECTION_NAME = "its_documentation"
    EMBEDDING_DIM = 384  # MiniLM-L12-v2 output dim
    BATCH_SIZE = 64

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
        chunker: Optional[ITSChunker] = None,
    ):
        self.qdrant_url = qdrant_url
        self.embedding_model = embedding_model
        self.chunker = chunker or ITSChunker()
        self._qdrant = None
        self._embedder = None

    def _get_qdrant(self):
        """Lazy-init Qdrant client."""
        if self._qdrant is None:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams

                self._qdrant = QdrantClient(url=self.qdrant_url)
                # Ensure collection exists
                collections = [
                    c.name for c in self._qdrant.get_collections().collections
                ]
                if self.COLLECTION_NAME not in collections:
                    self._qdrant.create_collection(
                        collection_name=self.COLLECTION_NAME,
                        vectors_config=VectorParams(
                            size=self.EMBEDDING_DIM,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info("Created Qdrant collection: %s", self.COLLECTION_NAME)
            except ImportError:
                logger.warning(
                    "qdrant-client not installed. Install: pip install qdrant-client"
                )
                raise
        return self._qdrant

    def _get_embedder(self):
        """Lazy-init sentence-transformers model."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer(self.embedding_model)
                logger.info("Loaded embedding model: %s", self.embedding_model)
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. Install: pip install sentence-transformers"
                )
                raise
        return self._embedder

    def _chunk_id(self, chunk: ITSChunk) -> str:
        """Generate deterministic ID for a chunk."""
        key = f"{chunk.source_file}:{chunk.section_title}:{chunk.chunk_index}"
        return hashlib.md5(key.encode()).hexdigest()

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts."""
        model = self._get_embedder()
        embeddings = model.encode(
            texts, show_progress_bar=False, normalize_embeddings=True
        )
        return embeddings.tolist()

    async def index_all(self, force: bool = False) -> dict:
        """Index all ITS documentation.

        Args:
            force: Re-index even if already indexed

        Returns:
            Stats dict with chunks_total, chunks_indexed, files_processed
        """
        chunks = self.chunker.chunk_all()
        logger.info("Chunked %d chunks from ITS documentation", len(chunks))

        if not chunks:
            return {"chunks_total": 0, "chunks_indexed": 0, "files_processed": 0}

        qdrant = self._get_qdrant()
        files_seen = set()
        indexed = 0

        # Process in batches
        for i in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[i : i + self.BATCH_SIZE]
            texts = [c.text for c in batch]

            # Embed batch
            vectors = self._embed_batch(texts)

            # Build Qdrant points
            from qdrant_client.models import PointStruct

            points = []
            for chunk, vector in zip(batch, vectors):
                point_id = self._chunk_id(chunk)
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "text": chunk.text,
                            "source_file": chunk.source_file,
                            "section_title": chunk.section_title,
                            "chunk_index": chunk.chunk_index,
                            "its_article_id": chunk.its_article_id,
                            "char_count": chunk.char_count,
                        },
                    )
                )
                files_seen.add(chunk.source_file)

            # Upsert to Qdrant
            qdrant.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points,
            )
            indexed += len(points)
            logger.info(
                "Indexed batch %d-%d (%d/%d)", i, i + len(batch), indexed, len(chunks)
            )

        stats = {
            "chunks_total": len(chunks),
            "chunks_indexed": indexed,
            "files_processed": len(files_seen),
        }
        logger.info("Indexing complete: %s", stats)
        return stats
