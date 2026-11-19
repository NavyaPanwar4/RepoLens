import chromadb
from app.services.embedder import embed_texts
from app.core.config import get_settings

def get_client():
    return chromadb.PersistentClient(path=str(get_settings().chroma_path))

def get_or_create_collection(repo_id: str):
    client = get_client()
    return client.get_or_create_collection(
        name=repo_id,
        metadata={"hnsw:space": "cosine"},
    )

def store_chunks(repo_id: str, chunks: list[dict]):
    """
    Embed and store all chunks into a Chroma collection.
    repo_id is used as the collection name — one collection per repo.
    """
    if not chunks:
        return 0

    collection = get_or_create_collection(repo_id)

    texts = [c["text"] for c in chunks]
    ids = [c["id"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    # Keep embedding and Chroma writes below provider/database limits.
    all_embeddings = []
    embed_batch_size = 32
    for i in range(0, len(texts), embed_batch_size):
        batch = texts[i:i + embed_batch_size]
        all_embeddings.extend(embed_texts(batch))

    # Chroma enforces a maximum batch size; large repositories can exceed it.
    chroma_batch_size = 1000
    for i in range(0, len(texts), chroma_batch_size):
        collection.upsert(
            ids=ids[i:i + chroma_batch_size],
            documents=texts[i:i + chroma_batch_size],
            embeddings=all_embeddings[i:i + chroma_batch_size],
            metadatas=metadatas[i:i + chroma_batch_size],
        )
    return len(chunks)

def query_chunks(repo_id: str, question: str, n_results: int = 8) -> list[dict]:
    """
    Embed a question and retrieve the top-n most relevant chunks.
    """
    from app.services.embedder import embed_single
    collection = get_or_create_collection(repo_id)
    chunk_count = collection.count()
    if chunk_count == 0:
        raise ValueError("This repository has not been indexed.")

    query_embedding = embed_single(question)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, chunk_count),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text": doc,
            "metadata": meta,
            "score": round(1 - dist, 4),  # cosine similarity
        })
    return hits

def delete_collection(repo_id: str):
    client = get_client()
    try:
        client.delete_collection(repo_id)
    except Exception:
        pass
