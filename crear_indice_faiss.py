import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Cargar modelo de embeddings (funciona offline si ya lo descargaste antes)
model = SentenceTransformer("all-MiniLM-L6-v2")

# Cargar tus chunks
with open("vector_index/chunks.json", "r", encoding="utf-8") as f:
    data = json.load(f)

texts = [item["content"] for item in data]
metadata = [
    {
        "chunk_id": item["chunk_id"],
        "source": item["source"],
        "page": item["page"]
    }
    for item in data
]

# Convertir a embeddings
embeddings = model.encode(texts)

# Crear índice FAISS
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(np.array(embeddings).astype("float32"))

# Guardar índice
faiss.write_index(index, "vector_index/index.faiss")

# Guardar metadatos
with open("vector_index/metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=4, ensure_ascii=False)

print("Índice FAISS generado correctamente.")