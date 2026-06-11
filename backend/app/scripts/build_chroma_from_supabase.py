import os
import chromadb
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv("DATABASE_URL")
CHROMA_PATH = os.getenv("CHROMA_PATH", "/tmp/chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "nui_ba_den_rag")
EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def build_document(row: dict, table_name: str) -> str:
    parts = [f"Nguồn bảng: {table_name}"]

    for key, value in row.items():
        if value is None:
            continue
        parts.append(f"{key}: {value}")

    return "\n".join(parts)


def fetch_table(engine, table_name: str):
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name}"))
        return [dict(row._mapping) for row in result]


def main():
    if not DATABASE_URL:
        raise RuntimeError("Missing DATABASE_URL")

    engine = create_engine(DATABASE_URL)

    tables = [
        "destinations",
        "services_pricing",
        "operation_hours",
        "activities",
        "faq",
        "knowledge_base",
    ]

    model = SentenceTransformer(EMBEDDING_MODEL)

    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass

    collection = client.create_collection(name=CHROMA_COLLECTION)

    ids = []
    documents = []
    metadatas = []

    for table_name in tables:
        rows = fetch_table(engine, table_name)

        for index, row in enumerate(rows):
            doc = build_document(row, table_name)

            ids.append(f"{table_name}_{index}")
            documents.append(doc)
            metadatas.append({
                "source": table_name,
                "row_index": index,
            })

    if not documents:
        print("No documents found from Supabase")
        return

    embeddings = model.encode(documents).tolist()

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Built Chroma collection '{CHROMA_COLLECTION}' with {len(documents)} documents")


if __name__ == "__main__":
    main()