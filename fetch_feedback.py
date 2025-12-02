# fetch_feedback.py
import csv
import requests
import time
from collections import defaultdict
from dotenv import load_dotenv
import os

load_dotenv()

MOODLE_TOKEN = os.getenv("MOODLE_TOKEN") or "934a5bc65d092299e862902196a6f43b"
MOODLE_DOMAIN = os.getenv("MOODLE_DOMAIN") or "https://campusvirtual-sifods.minedu.gob.pe"

def get_analysis(feedback_id):
    url = f"{MOODLE_DOMAIN}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "mod_feedback_get_responses_analysis",
        "feedbackid": feedback_id,
        "moodlewsrestformat": "json",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def export_feedback_to_csv(feedback_id, out_path="feedback_respuestas.csv"):
    data = get_analysis(feedback_id)

    rows = []
    intentos_por_usuario = defaultdict(int)

    attempts = sorted(data.get("attempts", []), key=lambda x: (x.get("userid"), x.get("timemodified",0)))

    for attempt in attempts:
        userid = attempt.get("userid")
        intentos_por_usuario[userid] += 1
        intento_num = intentos_por_usuario[userid]

        attempt_id = attempt.get("id")
        user = attempt.get("fullname","")
        timestamp = attempt.get("timemodified",0)
        fecha = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        for resp in attempt.get("responses", []):
            rows.append({
                "feedback_id": feedback_id,
                "userid": userid,
                "usuario": user,
                "attempt_id": attempt_id,
                "intento": intento_num,
                "fecha_respuesta": fecha,
                "pregunta_id": resp.get("id"),
                "pregunta": resp.get("name"),
                "respuesta": resp.get("rawval","")
            })

    if rows:
        # Guardar CSV con delimitador punto y coma para evitar problemas con comas en el texto
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print("CSV generado con", len(rows), "filas ->", out_path)
    else:
        print("No se encontraron respuestas para feedback", feedback_id)


if __name__ == "__main__":
    # ejemplo de uso
    FEEDBACK_ID = 12190
    export_feedback_to_csv(FEEDBACK_ID)