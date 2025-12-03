import csv
import requests
import time
from collections import defaultdict

MOODLE_TOKEN = "934a5bc65d092299e862902196a6f43b"
MOODLE_DOMAIN = "https://campusvirtual-sifods.minedu.gob.pe"

# ------------------------------------------
# 1. Obtener análisis general (intentos)
# ------------------------------------------
def get_analysis(feedback_id):
    url = f"{MOODLE_DOMAIN}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "mod_feedback_get_responses_analysis",
        "feedbackid": feedback_id,
        "moodlewsrestformat": "json",
    }
    return requests.get(url, params=params).json()

# ------------------------------------------
# 2. Obtener preguntas completas
# ------------------------------------------
def get_items(feedback_id):
    url = f"{MOODLE_DOMAIN}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "mod_feedback_get_items",
        "feedbackid": feedback_id,
        "moodlewsrestformat": "json",
    }
    return requests.get(url, params=params).json()

# ------------------------------------------
# 3. Obtener respuestas completas por intento
# ------------------------------------------
def get_full_responses(feedback_id, attempt_id):
    url = f"{MOODLE_DOMAIN}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "mod_feedback_get_responses",
        "feedbackid": feedback_id,
        "attemptid": attempt_id,
        "moodlewsrestformat": "json",
    }
    return requests.get(url, params=params).json()


feedback_id = 12283#12190

# Obtener intents
data = get_analysis(feedback_id)

# Obtener preguntas completas
items_data = get_items(feedback_id)
preguntas_completas = {
    str(item["id"]): item.get("name", "")
    for item in items_data.get("items", [])
}

rows = []
intentos_por_usuario = defaultdict(int)

# Ordenar intentos por usuario y fecha
attempts = sorted(data.get("attempts", []), key=lambda x: (x["userid"], x["timemodified"]))

for attempt in attempts:
    userid = attempt["userid"]
    intentos_por_usuario[userid] += 1
    intento_num = intentos_por_usuario[userid]

    attempt_id = attempt["id"]
    user = attempt["fullname"]
    timestamp = attempt["timemodified"]
    fecha = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

    # ------------------------------------------
    # RESPUESTAS COMPLETAS EN ESTE INTENTO
    # ------------------------------------------
    resp_full = get_full_responses(feedback_id, attempt_id)

    respuestas_completas = {}
    for i in resp_full.get("items", []):
        pid = str(i["item"]["id"])
        if i.get("responses"):
            respuestas_completas[pid] = i["responses"][0]

    # ------------------------------------------
    # PROCESAR RESPUESTAS
    # ------------------------------------------
    for resp in attempt["responses"]:
        pregunta_id = str(resp["id"])

        pregunta_texto = preguntas_completas.get(
            pregunta_id,
            resp["name"]  # fallback
        )

        respuesta_texto = respuestas_completas.get(
            pregunta_id,
            resp.get("rawval", "")  # fallback
        )

        rows.append({
            "feedback_id": feedback_id,
            "userid": userid,
            "usuario": user,
            "attempt_id": attempt_id,
            "intento": intento_num,
            "fecha_respuesta": fecha,
            "pregunta_id": pregunta_id,
            "pregunta": pregunta_texto,
            "respuesta": respuesta_texto
        })

# ------------------------------------------
# Guardar CSV final
# ------------------------------------------
with open("feedback_respuestas.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("CSV generado con", len(rows), "filas")