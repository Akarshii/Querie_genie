# rag_pipeline.py

from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from sel import scrape_website  # Import the Selenium scraper from sel.py

# Global objects shared across functions
chunks = []
embedder = None
index = None

def prepare_rag_pipeline(raw_text):
    """
    Prepares the FAISS index and embeddings from the input raw text.
    
    Args:
        raw_text (str): The full raw input text (scraped HTML, etc.)
    
    Sets:
        chunks (list): The split text chunks.
        embedder (SentenceTransformer): The embedding model.
        index (faiss.IndexFlatL2): The FAISS vector index.
    """
    global chunks, embedder, index

    # Step 1: Chunk the text
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(raw_text)

    # Step 2: Generate embeddings
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = embedder.encode(chunks, show_progress_bar=True)

    # Step 3: Create FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))

def retrieve_relevant_chunks(query, top_k=5):
    """Returns top-k most relevant chunks for the given query."""
    if index is None or embedder is None or not chunks:
        raise ValueError("RAG pipeline is not initialized. Call prepare_rag_pipeline() first.")

    q_emb = embedder.encode([query])
    scores, idxs = index.search(np.array(q_emb), top_k)
    return [chunks[i] for i in idxs[0]]