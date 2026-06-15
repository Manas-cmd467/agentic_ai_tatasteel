import os
import sys
import re
import hashlib
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from knowledge_base.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Default directories
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KNOWLEDGE_DIR = os.path.join(_THIS_DIR, '..', 'data', 'knowledge_docs')


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list:
    """
    Split *text* into overlapping word-level chunks.

    Args:
        text       : Raw input text.
        chunk_size : Maximum number of words per chunk.
        overlap    : Number of words shared between consecutive chunks.

    Returns:
        List of non-empty text chunk strings.
    """
    if not text or not text.strip():
        return []

    words = text.split()
    if len(words) <= chunk_size:
        return [text.strip()]

    chunks = []
    step = max(chunk_size - overlap, 1)
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        if end == len(words):
            break
        start += step

    return chunks


# ---------------------------------------------------------------------------
# Individual file ingestors
# ---------------------------------------------------------------------------

def ingest_txt_file(filepath: str, vs: VectorStore) -> int:
    """
    Read a plain-text (or Markdown) file, chunk it, and add to VectorStore.

    Returns:
        Number of chunks ingested.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except Exception as e:
        print(f"[ingest] ERROR reading '{filepath}': {e}")
        return 0

    chunks = chunk_text(text)
    if not chunks:
        print(f"[ingest] '{filepath}' yielded no chunks – skipping.")
        return 0

    source = os.path.basename(filepath)
    docs = []
    for i, chunk in enumerate(chunks):
        uid = hashlib.md5(f"{source}-{i}-{chunk[:40]}".encode()).hexdigest()
        docs.append(
            {
                "text": chunk,
                "source": source,
                "chunk_id": uid,
                "metadata": {
                    "file_type": os.path.splitext(filepath)[1].lstrip('.'),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            }
        )

    vs.add_documents(docs)
    print(f"[ingest] '{source}' -> {len(docs)} chunk(s) added.")
    return len(docs)


def ingest_pdf_file(filepath: str, vs: VectorStore) -> int:
    """
    Extract text from a PDF using PyMuPDF (fitz), chunk each page's text,
    and add to VectorStore.

    Returns:
        Number of chunks ingested.  Returns 0 gracefully if fitz is missing.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(
            "[ingest] PyMuPDF (fitz) is not installed – skipping PDF file "
            f"'{filepath}'.  Run: pip install pymupdf"
        )
        return 0

    try:
        doc = fitz.open(filepath)
    except Exception as e:
        print(f"[ingest] ERROR opening PDF '{filepath}': {e}")
        return 0

    source = os.path.basename(filepath)
    all_docs = []
    for page_num in range(len(doc)):
        try:
            page_text = doc[page_num].get_text("text")
        except Exception as e:
            print(f"[ingest] WARNING: Could not read page {page_num} of '{source}': {e}")
            continue

        if not page_text or not page_text.strip():
            continue

        chunks = chunk_text(page_text)
        for i, chunk in enumerate(chunks):
            uid = hashlib.md5(
                f"{source}-p{page_num}-{i}-{chunk[:40]}".encode()
            ).hexdigest()
            all_docs.append(
                {
                    "text": chunk,
                    "source": source,
                    "chunk_id": uid,
                    "metadata": {
                        "file_type": "pdf",
                        "page": page_num + 1,
                        "chunk_index": i,
                    },
                }
            )

    doc.close()

    if not all_docs:
        print(f"[ingest] '{source}' yielded no text – skipping.")
        return 0

    vs.add_documents(all_docs)
    print(f"[ingest] '{source}' -> {len(all_docs)} chunk(s) added.")
    return len(all_docs)


def ingest_csv_logs(csv_path: str, vs: VectorStore) -> int:
    """
    Read a maintenance-log CSV with pandas and convert each row to a
    descriptive text string, then add to VectorStore.

    Returns:
        Number of row-documents ingested.
    """
    try:
        import pandas as pd
    except ImportError:
        print("[ingest] pandas is not installed – skipping CSV ingestion. Run: pip install pandas")
        return 0

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[ingest] ERROR reading CSV '{csv_path}': {e}")
        return 0

    source = os.path.basename(csv_path)
    docs = []
    for idx, row in df.iterrows():
        parts = []
        for col, val in row.items():
            if pd.notna(val):
                parts.append(f"{col}: {val}")
        row_text = "Maintenance log entry – " + ", ".join(parts) + "."

        uid = hashlib.md5(f"{source}-row{idx}".encode()).hexdigest()
        docs.append(
            {
                "text": row_text,
                "source": source,
                "chunk_id": uid,
                "metadata": {
                    "file_type": "csv",
                    "row_index": int(idx),
                },
            }
        )

    if not docs:
        print(f"[ingest] CSV '{source}' contained no rows – skipping.")
        return 0

    vs.add_documents(docs)
    print(f"[ingest] '{source}' -> {len(docs)} row-document(s) added.")
    return len(docs)


# ---------------------------------------------------------------------------
# Directory-level ingestion
# ---------------------------------------------------------------------------

def ingest_all_documents(
    knowledge_dir: str,
    vs: Optional[VectorStore] = None,
) -> int:
    """
    Recursively iterate *knowledge_dir* and ingest all .txt, .pdf, and .md
    files into the VectorStore.

    Args:
        knowledge_dir : Absolute or relative path to the knowledge documents
                        directory.
        vs            : An existing VectorStore instance (created if None).

    Returns:
        Total number of chunks ingested across all files.
    """
    if vs is None:
        vs = VectorStore()

    knowledge_dir = os.path.abspath(knowledge_dir)

    if not os.path.isdir(knowledge_dir):
        print(f"[ingest] Knowledge directory does not exist: '{knowledge_dir}'")
        return 0

    supported_extensions = {'.txt', '.md', '.pdf'}
    total_chunks = 0

    for root, _dirs, files in os.walk(knowledge_dir):
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported_extensions:
                continue

            filepath = os.path.join(root, filename)
            print(f"[ingest] Processing: {filepath}")

            if ext == '.pdf':
                total_chunks += ingest_pdf_file(filepath, vs)
            else:  # .txt or .md
                total_chunks += ingest_txt_file(filepath, vs)

    print(f"[ingest] Ingestion complete. Total chunks added: {total_chunks}")
    return total_chunks


# ---------------------------------------------------------------------------
# Conditional ingestion entry point
# ---------------------------------------------------------------------------

def run_ingestion_if_needed(knowledge_dir: Optional[str] = None) -> None:
    """
    Check whether the VectorStore already has documents.
    If it is empty, run full ingestion from *knowledge_dir*.
    """
    if knowledge_dir is None:
        knowledge_dir = DEFAULT_KNOWLEDGE_DIR

    try:
        vs = VectorStore()
        stats = vs.get_collection_stats()
        total_docs = stats.get("total_documents", 0)

        if total_docs > 0:
            print(
                f"[ingest] VectorStore already contains {total_docs} document(s). "
                "Skipping ingestion."
            )
            return

        print("[ingest] VectorStore is empty – starting full ingestion...")
        total = ingest_all_documents(knowledge_dir, vs)
        print(f"[ingest] run_ingestion_if_needed complete. {total} chunk(s) ingested.")

    except Exception as e:
        print(f"[ingest] ERROR during run_ingestion_if_needed: {e}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest knowledge documents into the ChromaDB vector store."
    )
    parser.add_argument(
        '--dir',
        default=DEFAULT_KNOWLEDGE_DIR,
        help='Path to the knowledge documents directory.',
    )
    parser.add_argument(
        '--csv',
        default=None,
        help='Optional path to a maintenance-log CSV file to ingest.',
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset the vector store before ingestion.',
    )
    args = parser.parse_args()

    print("=== Maintenance Wizard – Document Ingestion Pipeline ===")
    vs = VectorStore()

    if args.reset:
        print("[ingest] Resetting vector store as requested...")
        vs.reset_collection()

    total = ingest_all_documents(args.dir, vs)

    if args.csv and os.path.isfile(args.csv):
        total += ingest_csv_logs(args.csv, vs)

    stats = vs.get_collection_stats()
    print(f"\n=== Ingestion Summary ===")
    print(f"  Chunks added this run : {total}")
    print(f"  Total in collection   : {stats['total_documents']}")
    print(f"  Collection name       : {stats['collection_name']}")
    print(f"  Embedding model       : {stats['embedding_model']}")
