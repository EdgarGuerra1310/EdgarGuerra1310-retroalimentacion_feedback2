# evaluador_gpt.py
import os
import json
import csv
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import docx
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

# ---------------- Config / paths ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MOODLE_TOKEN = os.getenv("MOODLE_TOKEN")
MOODLE_DOMAIN = os.getenv("MOODLE_DOMAIN")

FAISS_INDEX_PATH = "vector_index/index.faiss"
META_PATH = "vector_index/metadata.json"
EXPECTED_CSV = "expected_answers.csv"   # usa ; como separador en tu CSV
RUBRICS_JSON = "rubrics.json"
TRANSCRIP_PATH = "data/Aprendizaje_accion_curso2.docx"

# ---------------- Inicializar OpenAI CAPI cliente ----------------
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------- Embedding model ----------------
EMBED_MODEL = "all-MiniLM-L6-v2"  # puedes usar otro, pero mantener coherencia
embedder = SentenceTransformer(EMBED_MODEL)

# ---------------- Cargar FAISS y metadata ----------------
print("Cargando FAISS index y metadata...")
index = faiss.read_index(FAISS_INDEX_PATH)
with open(META_PATH, "r", encoding="utf-8") as f:
    metadata = json.load(f)  # metadata expected to be a list aligned with index

# ---------------- Cargar expected answers ----------------
expected_map = {}
if os.path.exists(EXPECTED_CSV):
    # try both separators ; and ,
    with open(EXPECTED_CSV, newline="", encoding="utf-8") as f:
        # attempt detect delimiter: look at header
        sample = f.read(2000)
        f.seek(0)
        delimiter = ";" if ";" in sample.splitlines()[0] else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            pid = str(row.get("pregunta_id") or row.get("preguntaid") or row.get("id") or "").strip()
            if pid:
                expected_map[pid] = {
                    "pregunta": row.get("pregunta","").strip(),
                    "expected_text": row.get("expected_text","").strip()
                }

# ---------------- Cargar rubrics ----------------
rubrics_map = {}
if os.path.exists(RUBRICS_JSON):
    with open(RUBRICS_JSON, "r", encoding="utf-8") as f:
        rubrics_map = json.load(f)

# ---------------- Cargar transcripción DOCX ----------------
transcripcion_text = ""
if os.path.exists(TRANSCRIP_PATH):
    try:
        doc = docx.Document(TRANSCRIP_PATH)
        transcripcion_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        transcripcion_text = ""
        print("Error leyendo docx:", e)

# ---------------- Utilities ----------------
def embed_texts(texts):
    embs = embedder.encode(texts, show_progress_bar=False)
    return np.array(embs).astype("float32")

def buscar_chunks_por_query(query, top_k=5):
    # embed query
    q_emb = embed_texts([query])
    D, I = index.search(q_emb, top_k)
    results = []
    for dist, idx in zip(D[0], I[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        meta = metadata[idx].copy() if isinstance(metadata, list) else dict(metadata.get(str(idx), {}))
        # include snippet if present
        snippet = meta.get("content") or meta.get("snippet") or meta.get("text") or ""
        meta_out = {
            "source": meta.get("source", ""),
            "page": meta.get("page", meta.get("pageno", None)),
            "snippet": snippet,
            "score": float(dist)
        }
        results.append(meta_out)
    return results

def similitud_con_expected(respuesta_text, expected_text):
    if not respuesta_text or not expected_text:
        return 0.0
    embs = embed_texts([respuesta_text, expected_text])
    sim = cosine_similarity([embs[0]], [embs[1]])[0][0]
    return float(np.clip(sim, 0.0, 1.0))

def map_sim_to_level(sim, thresholds=[0.30, 0.55, 0.75], labels=["Insuficiente","En proceso","Satisfactorio","Destacado"]):
    t0,t1,t2 = thresholds
    if sim < t0:
        return labels[0]
    elif sim < t1:
        return labels[1]
    elif sim < t2:
        return labels[2]
    else:
        return labels[3]

def rubric_to_text(rubric_obj):
    if not rubric_obj:
        return ""
    # simple rubric: criterion + levels
    if "criterion" in rubric_obj and "levels" in rubric_obj:
        out = [f"Criterio: {rubric_obj.get('criterion','')}"]
        for nivel, desc in rubric_obj.get("levels", {}).items():
            out.append(f"- {nivel}: {desc}")
        return "\n".join(out)
    # complex rubric
    if "criteria" in rubric_obj:
        out = [rubric_obj.get("title","Rúbrica")]
        for crit in rubric_obj.get("criteria", []):
            out.append(f"\nCriterio: {crit.get('name')}")
            out.append(f"- Insuficiente: {crit.get('Insuficiente')}")
            out.append(f"- En proceso: {crit.get('En proceso')}")
            out.append(f"- Satisfactorio: {crit.get('Satisfactorio')}")
            out.append(f"- Destacado: {crit.get('Destacado')}")
        return "\n".join(out)
    return json.dumps(rubric_obj, ensure_ascii=False)

# ---------------- Prompt builder & GPT call ----------------
def construir_prompt(pregunta, respuesta, expected_text, rubric_text, chunks, transcripcion):
    contexto_chunks = ""
    for c in chunks[:4]:
        contexto_chunks += f"[{c.get('source','?')} - pág {c.get('page','?')}] {c.get('snippet','')}\n\n"

    trans = f"\n\nTRANSCRIPCIÓN DEL VIDEO:\n{transcripcion}\n\n" if transcripcion else ""

    prompt = f"""
Eres un evaluador experto del MINEDU. Usa SOLO la información provista (fascículos y transcripción).
No inventes contenido.

CONTEXTOS RELEVANTES (extractos):
{contexto_chunks}

{trans}

PREGUNTA:
{pregunta}

RESPUESTA DEL ESTUDIANTE:
{respuesta}

RESPUESTA ESPERADA:
{expected_text}

RÚBRICA:
{rubric_text}

INSTRUCCIONES:
0) Eres un formador que brinda retroalimentación, escribe como si estarías dando retroalimentación directa.
1) Devuelve SOLO un texto claro y estructurado para el docente.
2) Incluye:
   - Nivel logrado (Insuficiente, En proceso, Satisfactorio o Destacado)
   - Razones pedagógicas
   - Evidencia de los fascículos (máx 2)
   - Recomendaciones concretas para mejorar
3) NO devuelvas JSON. NO uses llaves {{}}. NO uses bloques ```json.
4) Escribe un texto limpio sin formato especial.
"""
    return prompt


def construir_prompt_rubrica_compleja(pregunta, respuesta, expected_text, rubric_entry, chunks, transcripcion):
    # Construimos texto de contexto igual al prompt normal
    contexto_chunks = ""
    for c in chunks[:4]:
        contexto_chunks += f"[{c.get('source','?')} - pág {c.get('page','?')}] {c.get('snippet','')}\n\n"

    trans = f"\n\nTRANSCRIPCIÓN DEL VIDEO:\n{transcripcion}\n\n" if transcripcion else ""

    # Crear texto estructurado por criterios
    criterios_texto = ""
    for crit in rubric_entry.get("criteria", []):
        criterios_texto += f"\nCRITERIO: {crit.get('name')}\n"
        criterios_texto += f"- Nivel Pre-reflexivo (Transición A hacia B): {crit.get('Nivel Pre-reflexivo (Transición A hacia B)')}\n"
        criterios_texto += f"- Nivel reflexión superficial (Transición B hacia C): {crit.get('Nivel reflexión superficial (Transición B hacia C)')}\n"
        criterios_texto += f"- Nivel reflexión pedagógica (Transición C hacia D): {crit.get('Nivel reflexión pedagógica (Transición C hacia D)')}\n"
        criterios_texto += f"- Nivel reflexión crítica (Consolidación): {crit.get('Nivel reflexión crítica (Consolidación)')}\n"

    prompt = f"""
Eres un evaluador experto del MINEDU. Usa SOLO la información de los fascículos y la transcripción. No inventes contenido.

CONTEXTOS RELEVANTES:
{contexto_chunks}
{trans}

PREGUNTA:
{pregunta}

RESPUESTA DEL ESTUDIANTE:
{respuesta}

RESPUESTA ESPERADA:
{expected_text}

RÚBRICA (evaluación por criterios):
{criterios_texto}

INSTRUCCIONES:
0) Eres un formador que brinda retroalimentación, escribe como si estarías dando retroalimentación directa. Escribe en primera persona.
1) Devuelve SOLO un texto claro y estructurado para el docente.
2) Incluye:
   - Nivel logrado (Nivel Pre-reflexivo (Transición A hacia B),Nivel reflexión superficial (Transición B hacia C),Nivel reflexión pedagógica (Transición C hacia D) o Nivel reflexión crítica (Consolidación))
   - Valoración inicial: Reconocemos el cumplimiento formal de la actividad de narración, lo cual evidencia su compromiso con el programa. Sin embargo, observamos la ausencia de un análisis introspectivo de su práctica.
   - Fundamento conceptual: Su análisis muestra una tendencia a la atribución externa, lo cual está asociado al nivel pre-reflexivo (o racionalidad descriptiva). El programa busca que transite hacia la racionalidad práctica, que exige que la reflexión parta de la práctica propia y la toma de decisiones.   
   - Orientación de mejora: Oriéntese a centrar el foco en sus propias acciones y decisiones. En lugar de culpar a factores externos, describa si la estrategia utilizada fue o no eficaz para el objetivo propuesto, y qué decisiones tomó usted para mitigar la frustración en el aula, como lo sugiere el rol de formador.
   - Recomendación de profundización: Usted menciona que la dificultad se debe al desinterés del docente. Si consideramos el principio andragógico de la autonomía (Curso 1), ¿qué acciones específicas de su mediación limitaron o no promovieron la autodirección del participante en ese taller? 
3) NO devuelvas JSON, nada entre llaves y sin formato raro.
4) Escribe un texto limpio.
"""

    return prompt

def construir_prompt_rubrica_niveles(pregunta, respuesta, expected_text, rubrica_entry, chunks, transcripcion):

    contexto_chunks = ""
    for c in chunks[:4]:
        contexto_chunks += f"[{c.get('source','?')} - pág {c.get('page','?')}] {c.get('snippet','')}\n\n"

    trans = f"\n\nTRANSCRIPCIÓN DEL VIDEO:\n{transcripcion}\n\n" if transcripcion else ""

    niveles_text = ""
    for nivel, descripcion in rubrica_entry.get("levels", {}).items():
        niveles_text += f"\n🔹 **{nivel}**:\n{descripcion}\n"

    prompt = f"""
Eres un evaluador experto del MINEDU. Evalúa la respuesta del formador usando EXCLUSIVAMENTE los textos dados, las evidencias y la rúbrica oficial.

CONTEXTOS RELEVANTES:
{contexto_chunks}
{trans}

PREGUNTA:
{pregunta}

RESPUESTA DEL ESTUDIANTE:
{respuesta}

RESPUESTA ESPERADA (si aplica):
{expected_text}

RÚBRICA DE NIVELES DE REFLEXIÓN:
{niveles_text}

INSTRUCCIONES:
0) Brinda retroalimentación profesional, directa y respetuosa. escribe en primera persona.
1) Tu salida debe incluir ÚNICAMENTE:
   - El **nivel donde se ubica** la respuesta.
   - Una **Valoración inicial** basada en:
       * reconocer el esfuerzo del participante,
       * señalar si falta introspección,
       * identificar si la respuesta es meramente descriptiva.
   - Un **Fundamento conceptual** basado en:
       * la relación entre la respuesta y la rúbrica,
       * identificación del tipo de racionalidad (descriptiva, práctica, pedagógica o crítica),
       * análisis del foco (externo vs interno).
   - Una **Orientación de mejora** basada en:
       * centrar análisis en acciones propias,
       * conectar decisiones tomadas con el objetivo pedagógico,
       * indicar cómo podría mejorar su mediación.
   - Una **Recomendación de profundización** basada en:
       * principios andragógicos,
       * relación entre la práctica y la toma de decisiones,
       * una pregunta o invitación concreta para reflexionar a mayor nivel.

2) No utilices exactamente los textos guía; úsalos como REFERENTE conceptual para elaborar tu propio contenido.
3) No evalúes criterio por criterio.
4) No devuelvas JSON ni llaves. Escribe un texto limpio.
    """

    return prompt

#def pedir_evaluacion_a_gpt(pregunta, respuesta, expected_text, rubric_text, chunks, transcripcion):
#    prompt = construir_prompt(pregunta, respuesta, expected_text, rubric_text, chunks, transcripcion)
#    completion = client.chat.completions.create(
#        model="gpt-4.1-mini",
#        messages=[
#            {"role":"system","content":"Eres un asistente que evalúa respuestas docentes basándose en documentos oficiales."},
#            {"role":"user","content":prompt}
#        ],
#        temperature=0.0,
#        max_tokens=700
#    )
#    content = completion.choices[0].message.content
#
#    return {"texto": content}
# ---------------- Función principal pública ----------------

#def pedir_evaluacion_a_gpt(pregunta, respuesta, expected_text, rubric_text, chunks, transcripcion, pregunta_id=None, rubrica_entry=None):
#    
#    # Si es la rúbrica compleja 68264 → usar prompt especial
#    if str(pregunta_id) == "68264" and rubrica_entry and "criteria" in rubrica_entry:
#        prompt = construir_prompt_rubrica_compleja(
#            pregunta, respuesta, expected_text, rubrica_entry, chunks, transcripcion
#        )
#    else:
#        # Mantener comportamiento normal
#        prompt = construir_prompt(
#            pregunta, respuesta, expected_text, rubric_text, chunks, transcripcion
#        )
#
#    completion = client.chat.completions.create(
#        model="gpt-4.1-mini",
#        messages=[
#            {"role": "system", "content": "Eres un asistente que evalúa respuestas docentes basándose en documentos oficiales."},
#            {"role": "user", "content": prompt}
#        ],
#        temperature=0.0,
#        max_tokens=900
#    )
#
#    content = completion.choices[0].message.content
#    return {"texto": content}
#

def pedir_evaluacion_a_gpt(pregunta, respuesta, expected_text, rubric_text, chunks, transcripcion,
                           pregunta_id=None, rubrica_entry=None):

    # Caso especial: ID 68264 con rúbrica de niveles
    if str(pregunta_id) == "68264" and rubrica_entry and "levels" in rubrica_entry:
        prompt = construir_prompt_rubrica_niveles(
            pregunta, respuesta, expected_text, rubrica_entry, chunks, transcripcion
        )

    else:
        # Caso normal para todas las otras preguntas
        prompt = construir_prompt(
            pregunta, respuesta, expected_text, rubric_text, chunks, transcripcion
        )

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Eres un asistente que evalúa respuestas docentes basándose en documentos oficiales."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=1100
    )

    return {"texto": completion.choices[0].message.content}

def evaluar_pregunta_con_contexto(pregunta, respuesta, pregunta_id=None, top_k=5):
    # retrieval
    query = (pregunta or "") + " " + (respuesta or "")
    chunks = buscar_chunks_por_query(query, top_k=top_k)

    # expected & rubric
    expected_entry = expected_map.get(str(pregunta_id), {})
    expected_text = expected_entry.get("expected_text", "")
    rubric_entry = rubrics_map.get(str(pregunta_id))
    rubric_text = rubric_to_text(rubric_entry) if rubric_entry else ""

    # similarity numeric
    sim = similitud_con_expected(respuesta, expected_text) if expected_text else 0.0
    level_est = map_sim_to_level(sim)

    # GPT evaluation
    gpt_eval = pedir_evaluacion_a_gpt(
    pregunta,
    respuesta,
    expected_text,
    rubric_text,
    chunks,
    transcripcion_text,
    pregunta_id=pregunta_id,
    rubrica_entry=rubric_entry
)

    # final structure
    return {
        "pregunta": pregunta,
        "pregunta_id": pregunta_id,
        "respuesta": respuesta,
        "similarity_score": sim,
        "level_estimate": level_est,
        "chunks_retrieved": chunks,
        "gpt_evaluation": gpt_eval
    }