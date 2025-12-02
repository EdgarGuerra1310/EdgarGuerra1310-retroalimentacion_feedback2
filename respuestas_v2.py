import csv
import requests
import time
from collections import defaultdict

MOODLE_TOKEN = "934a5bc65d092299e862902196a6f43b"
MOODLE_DOMAIN = "https://campusvirtual-sifods.minedu.gob.pe"

def get_analysis(feedback_id):
    url = f"{MOODLE_DOMAIN}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "mod_feedback_get_responses_analysis",
        "feedbackid": feedback_id,
        "moodlewsrestformat": "json",
    }
    return requests.get(url, params=params).json()

feedback_id = 12190  

data = get_analysis(feedback_id)

rows = []

# Para contar intentos por usuario
intentos_por_usuario = defaultdict(int)

# Ordenar por usuario y fecha
attempts = sorted(data.get("attempts", []), key=lambda x: (x["userid"], x["timemodified"]))

for attempt in attempts:
    userid = attempt["userid"]
    intentos_por_usuario[userid] += 1  # Incrementa el intento
    intento_num = intentos_por_usuario[userid]

    attempt_id = attempt["id"]
    user = attempt["fullname"]
    timestamp = attempt["timemodified"]
    fecha = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

    for resp in attempt["responses"]:
        rows.append({
            "feedback_id": feedback_id,
            "userid": userid,
            "usuario": user,
            "attempt_id": attempt_id,
            "intento": intento_num,
            "fecha_respuesta": fecha,
            "pregunta_id": resp["id"],
            "pregunta": resp["name"],
            "respuesta": resp["rawval"]
        })

# Guardar CSV
with open("feedback_respuestas.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("CSV generado con", len(rows), "filas")