from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

documents = []
embeddings = None
index = None


def add_documents(text):
    global documents, embeddings, index

    # Break text into chunks
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
    documents.extend(chunks)

    new_embeddings = model.encode(chunks)

    if embeddings is None:
        embeddings = np.array(new_embeddings).astype("float32")
    else:
        embeddings = np.vstack((embeddings, new_embeddings)).astype("float32")

    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)


def retrieve(query, top_k=3):
    global embeddings, index, documents

    if index is None:
        return ""

    query_embedding = model.encode([query]).astype("float32")
    distances, indices = index.search(query_embedding, top_k)

    results = [documents[i] for i in indices[0]]
    return "\n".join(results)
