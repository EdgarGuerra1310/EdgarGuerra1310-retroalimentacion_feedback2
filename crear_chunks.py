import os
import re
import glob
import json
from pypdf import PdfReader

# ============================================================
# --------- 1. Función para chunkear PDFs con páginas --------
# ============================================================

def chunk_pdf(file_path, max_chars=1200):
    reader = PdfReader(file_path)
    chunks = []
    filename = os.path.basename(file_path)

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if not text:
            continue

        text = re.sub(r'\s+', ' ', text).strip()

        chunk_index = 1
        for i in range(0, len(text), max_chars):
            chunk_text = text[i:i + max_chars]

            chunks.append({
                "chunk_id": f"{filename}_p{page_number}_c{chunk_index}",
                "source": filename,
                "page": page_number,
                "content": chunk_text
            })

            chunk_index += 1

    return chunks


# ============================================================
# -------- 2. Generar chunks SOLO DE PDF ----------------------
# ============================================================

def generar_chunks():
    os.makedirs("vector_index", exist_ok=True)

    all_chunks = []

    # Procesar solo PDFs
    pdf_files = glob.glob("data/*.pdf")
    for pdf in pdf_files:
        print(f"Procesando PDF: {pdf}")
        pdf_chunks = chunk_pdf(pdf)
        all_chunks.extend(pdf_chunks)

    # Guardar JSON
    output_path = "vector_index/chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print("\n=============================================")
    print(f"Total chunks generados (solo PDFs): {len(all_chunks)}")
    print(f"Archivo generado: {output_path}")
    print("=============================================\n")


if __name__ == "__main__":
    generar_chunks()