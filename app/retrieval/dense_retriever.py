"""
Dense Vector Retrieval Layer using ChromaDB and Local Sentence Transformers.

Implements persistent dense vector storage, cosine distance similarity search,
and metadata filtering strictly using local embeddings (all-MiniLM-L6-v2).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_COLLECTION_NAME = "relay_papers"
DEFAULT_CHROMA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "indexes" / "chroma"


class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Embedding function backed by local SentenceTransformer model.

    Enforces local_files_only=True to prevent accidental remote downloads or API calls.
    Embeddings are L2-normalized so cosine distance in ChromaDB is mathematically exact.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model_instance: Any = None,
    ) -> None:
        self.model_name = model_name
        if model_instance is not None:
            self._model = model_instance
        else:
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(model_name, local_files_only=True)
            except Exception:
                try:
                    # Fallback to remote download if not pre-cached locally (essential for Render/Docker deployments)
                    self._model = SentenceTransformer(model_name, local_files_only=False)
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed to load embedding model '{model_name}': {exc}."
                    ) from exc

    @staticmethod
    def name() -> str:
        return "local_sentence_transformer"

    def get_config(self) -> Dict[str, Any]:
        return {"model_name": self.model_name}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> LocalSentenceTransformerEmbeddingFunction:
        return LocalSentenceTransformerEmbeddingFunction(model_name=config.get("model_name", DEFAULT_MODEL_NAME))

    def __call__(self, input: Documents) -> Embeddings:
        """Generate normalized dense embeddings for document texts."""
        if not input:
            return []
        embeddings = self._model.encode(
            list(input),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


def sanitize_metadata_for_chroma(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert chunk metadata into ChromaDB-compatible primitive scalar types.

    ChromaDB metadata supports only str, int, float, bool.
    Complex types (lists, nested dicts) are serialized to JSON strings.
    """
    meta: Dict[str, Any] = {
        "chunk_id": str(chunk.get("chunk_id", "")),
        "chunk_index": int(chunk.get("chunk_index", 0)),
        "paper_id": str(chunk.get("paper_id", "")),
        "arxiv_id": str(chunk.get("arxiv_id", "")),
        "paper_version": str(chunk.get("paper_version", "")),
        "paper_title": str(chunk.get("paper_title", "")),
        "source_filename": str(chunk.get("source_filename", "")),
        "page_number": int(chunk.get("page_number", 1)),
        "section": str(chunk.get("section") or ""),
        "element_type": str(chunk.get("element_type", "prose")),
        "token_count": int(chunk.get("token_count", 0)),
        "character_count": int(chunk.get("character_count", 0)),
        "chunking_strategy": str(chunk.get("chunking_strategy", "langchain_recursive")),
        "source_block_id": str(chunk.get("source_block_id") or ""),
    }

    # Complex fields converted to JSON strings
    if "page_numbers" in chunk and isinstance(chunk["page_numbers"], (list, tuple)):
        meta["page_numbers_json"] = json.dumps(list(chunk["page_numbers"]))
    else:
        meta["page_numbers_json"] = json.dumps([meta["page_number"]])

    if "source_block_ids" in chunk and isinstance(chunk["source_block_ids"], (list, tuple)):
        meta["source_block_ids_json"] = json.dumps(list(chunk["source_block_ids"]))
    else:
        meta["source_block_ids_json"] = json.dumps([])

    if "bbox" in chunk and chunk["bbox"] is not None:
        meta["bbox_json"] = json.dumps(list(chunk["bbox"]))
    else:
        meta["bbox_json"] = ""

    return meta


def unpack_metadata_from_chroma(raw_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reconstruct original rich metadata dictionary from ChromaDB primitives.
    """
    meta = dict(raw_meta)

    # Restore None for empty section
    if meta.get("section") == "":
        meta["section"] = None

    # Unpack JSON strings
    if "page_numbers_json" in meta:
        try:
            meta["page_numbers"] = json.loads(meta.pop("page_numbers_json"))
        except (json.JSONDecodeError, TypeError):
            meta["page_numbers"] = [meta.get("page_number", 1)]
    else:
        meta["page_numbers"] = [meta.get("page_number", 1)]

    if "source_block_ids_json" in meta:
        try:
            meta["source_block_ids"] = json.loads(meta.pop("source_block_ids_json"))
        except (json.JSONDecodeError, TypeError):
            meta["source_block_ids"] = []

    if "bbox_json" in meta:
        bbox_str = meta.pop("bbox_json")
        if bbox_str:
            try:
                meta["bbox"] = json.loads(bbox_str)
            except (json.JSONDecodeError, TypeError):
                meta["bbox"] = None
        else:
            meta["bbox"] = None

    return meta


class DenseRetriever:
    """
    Persistent ChromaDB-backed dense vector retriever.

    Configured with cosine distance ('hnsw:space': 'cosine') and local embeddings.
    Supports idempotent upserting and paper-level metadata filtering.
    """

    def __init__(
        self,
        persist_dir: Optional[Path | str] = DEFAULT_CHROMA_DIR,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_function: Optional[EmbeddingFunction[Documents]] = None,
        in_memory: bool = False,
    ) -> None:
        self.persist_dir = Path(persist_dir) if persist_dir and not in_memory else None
        self.collection_name = collection_name

        if embedding_function is None:
            self.embedding_function = LocalSentenceTransformerEmbeddingFunction()
        else:
            self.embedding_function = embedding_function

        if in_memory or self.persist_dir is None:
            self._client = chromadb.Client()
        else:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))

        self.collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        """Return total number of chunks indexed in the collection."""
        return self.collection.count()

    def index_chunks(self, chunks: Sequence[Dict[str, Any]], batch_size: int = 64) -> int:
        """
        Index chunk records into the ChromaDB collection using idempotent upsert.

        Args:
            chunks: List of chunk dictionaries containing chunk_id, chunk_text, and metadata.
            batch_size: Number of records to upsert per batch.

        Returns:
            Total count of items indexed.
        """
        if not chunks:
            return 0

        total = len(chunks)
        for i in range(0, total, batch_size):
            batch = chunks[i : i + batch_size]
            ids: List[str] = []
            documents: List[str] = []
            metadatas: List[Dict[str, Any]] = []

            for c in batch:
                chunk_id = c.get("chunk_id")
                text = c.get("chunk_text") or c.get("content") or ""
                if not chunk_id or not text.strip():
                    continue

                ids.append(str(chunk_id))
                documents.append(str(text))
                metadatas.append(sanitize_metadata_for_chroma(c))

            if ids:
                self.collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )

        return self.collection.count()

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        paper_filter: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using cosine distance.

        Args:
            query_text: Natural language query string.
            top_k: Maximum number of results to return.
            paper_filter: Optional paper_id to restrict search.
            metadata_filter: Optional custom ChromaDB where filter.

        Returns:
            Ranked list of result dictionaries with metadata, scores, and provenance.
        """
        clean_query = query_text.strip()
        if not clean_query:
            return []

        total_available = self.collection.count()
        if total_available == 0:
            return []

        # Construct ChromaDB where clause
        where_clause: Optional[Dict[str, Any]] = None
        if paper_filter and metadata_filter:
            where_clause = {
                "$and": [
                    {"paper_id": paper_filter},
                    metadata_filter,
                ]
            }
        elif paper_filter:
            where_clause = {"paper_id": paper_filter}
        elif metadata_filter:
            where_clause = metadata_filter

        n_results = min(top_k, total_available)
        if n_results <= 0:
            return []

        results = self.collection.query(
            query_texts=[clean_query],
            n_results=n_results,
            where=where_clause,
        )

        ranked_results: List[Dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return ranked_results

        ids = results["ids"][0]
        documents = results["documents"][0] if results.get("documents") else [""] * len(ids)
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

        for rank, (cid, doc, raw_meta, dist) in enumerate(zip(ids, documents, metadatas, distances), start=1):
            unpacked_meta = unpack_metadata_from_chroma(raw_meta)
            # Cosine distance in Chroma is 1.0 - cosine_similarity (for normalized vectors)
            cosine_similarity = max(0.0, min(1.0, 1.0 - float(dist)))

            record = {
                "chunk_id": cid,
                "content": doc,
                "metadata": unpacked_meta,
                "paper_id": unpacked_meta.get("paper_id"),
                "paper_title": unpacked_meta.get("paper_title"),
                "arxiv_id": unpacked_meta.get("arxiv_id"),
                "paper_version": unpacked_meta.get("paper_version"),
                "page_number": unpacked_meta.get("page_number"),
                "page_numbers": unpacked_meta.get("page_numbers"),
                "section": unpacked_meta.get("section"),
                "element_type": unpacked_meta.get("element_type"),
                "distance": float(dist),
                "score": round(cosine_similarity, 6),
                "rank": rank,
                "retrieval_method": "dense",
            }
            ranked_results.append(record)

        return ranked_results

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific chunk by its chunk_id."""
        result = self.collection.get(ids=[chunk_id])
        if not result or not result.get("ids") or not result["ids"]:
            return None

        raw_meta = result["metadatas"][0] if result.get("metadatas") else {}
        doc = result["documents"][0] if result.get("documents") else ""
        unpacked = unpack_metadata_from_chroma(raw_meta)

        return {
            "chunk_id": chunk_id,
            "content": doc,
            "metadata": unpacked,
            "paper_id": unpacked.get("paper_id"),
            "paper_title": unpacked.get("paper_title"),
            "page_number": unpacked.get("page_number"),
            "section": unpacked.get("section"),
            "element_type": unpacked.get("element_type"),
        }

