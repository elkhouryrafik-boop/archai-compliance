"""Optional retrieval index (ChromaDB), built at runtime into a git-ignored folder.

Basis: file -> fixed-size chunks -> embeddings -> Chroma upsert. OpenAI embeddings are only
requested with ``embeddings='openai'`` (key from the environment); the default uses Chroma's
local default embedder.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

CHUNK_CHARS = 1000


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    text = text.strip()
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []


def read_chunks(path: Path) -> list[dict[str, str]]:
    """Chunk a .md/.txt/.pdf file into ``{"id", "text"}`` dicts."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        pages = [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    else:
        pages = [path.read_text(encoding="utf-8")]
    return [
        {"id": f"p{pi}_c{ci}", "text": t}
        for pi, page in enumerate(pages)
        for ci, t in enumerate(chunk_text(page))
    ]


def build_index(
    source: Path, db_dir: Path, collection: str = "regulation", embeddings: str = "default"
) -> int:
    import chromadb

    chunks = read_chunks(source)
    col = chromadb.PersistentClient(path=str(db_dir)).get_or_create_collection(collection)
    texts = [c["text"] for c in chunks]
    ids = [c["id"] for c in chunks]
    kwargs: dict[str, Any] = {}
    if embeddings == "openai":
        from archai.llm import get_client

        model = os.environ.get("ARCHAI_EMBED_MODEL") or "text-embedding-3-small"
        resp = get_client().embeddings.create(model=model, input=texts)
        kwargs["embeddings"] = [e.embedding for e in resp.data]
    col.upsert(ids=ids, documents=texts, **kwargs)
    return len(chunks)
