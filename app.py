# app.py
import os
import logging
from flask import Flask, request, render_template
import requests
from collections import defaultdict
import time
from dotenv import load_dotenv

import psycopg2
from psycopg2.extras import RealDictCursor
import os


load_dotenv()

MOODLE_TOKEN = os.getenv("MOODLE_TOKEN")
MOODLE_DOMAIN = os.getenv("MOODLE_DOMAIN")


if not MOODLE_TOKEN or not MOODLE_DOMAIN:
    raise ValueError("Faltan variables de entorno: MOODLE_TOKEN o MOODLE_DOMAIN")

from evaluador_gpt import evaluar_pregunta_con_contexto

app = Flask(__name__, template_folder="templates", static_folder="static")

logging.basicConfig(level=logging.INFO, filename="app.log", format="%(asctime)s - %(levelname)s - %(message)s")



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

#@app.route("/feedback/", methods=["GET"])
#def feedback_view():
#    id_user = request.args.get("id_user") or request.args.get("id") or request.args.get("userid")
#    feedbackid = request.args.get("feedbackid")
#    nombre_usuario = request.args.get("nombre_usuario") or request.args.get("nombre") or "Usuario"
#
#    if not id_user or not feedbackid:
#        return "Faltan parámetros. Usa ?id_user=...&feedbackid=...&nombre_usuario=...", 400
#
#    try:
#        data = get_analysis(feedbackid)
#    except Exception as e:
#        logging.exception("Error consultando Moodle")
#        return f"Error al obtener datos de Moodle: {e}", 500
#
#    attempts = data.get("attempts", [])
#    user_attempts = [a for a in attempts if str(a.get("userid")) == str(id_user)]
#    if not user_attempts:
#        return f"No se encontraron intentos para usuario {id_user} en feedback {feedbackid}", 200
#
#    # ordenar por timemodified
#    attempts_sorted = sorted(user_attempts, key=lambda x: x.get("timemodified", 0))
#
#    results = []  # lista de item por cada respuesta (mantener orden)
#    intentos_por_usuario = defaultdict(int)
#
#    for attempt in attempts_sorted:
#        uid = attempt.get("userid")
#        intentos_por_usuario[uid] += 1
#        intento_num = intentos_por_usuario[uid]
#        ts = attempt.get("timemodified", 0)
#        fecha = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
#
#        for resp in attempt.get("responses", []):
#            pregunta_id = str(resp.get("id"))
#            pregunta_text = resp.get("name") or ""
#            respuesta_text = (resp.get("rawval") or "").strip()
#
#            # Evaluar
#            try:
#                eval_result = evaluar_pregunta_con_contexto(pregunta_text, respuesta_text, pregunta_id)
#            except Exception as e:
#                logging.exception("Error en evaluación")
#                eval_result = {
#                    "pregunta": pregunta_text,
#                    "pregunta_id": pregunta_id,
#                    "respuesta": respuesta_text,
#                    "similarity_score": 0.0,
#                    "level_estimate": "Error",
#                    "chunks_retrieved": [],
#                    "gpt_evaluation": {"error_parse": "exception", "raw": str(e)}
#                }
#
#            results.append({
#                "userid": uid,
#                "usuario": attempt.get("fullname", nombre_usuario),
#                "attempt_id": attempt.get("id"),
#                "intento": intento_num,
#                "fecha": fecha,
#                "pregunta_id": pregunta_id,
#                "pregunta": pregunta_text,
#                "respuesta": respuesta_text,
#                "evaluation": eval_result
#            })
#
#    # render
#    # Agrupar por intento
#    by_intent = {}
#    for item in results:
#        intento = item.get("intento", 1)
#        if intento not in by_intent:
#            by_intent[intento] = []
#        by_intent[intento].append(item)
#
#    print("======== DEBUG RESULTS ========")
#    print(pregunta_id)
#    print("Total:", len(pregunta_id))
#    print("===============================")
#
#    return render_template(
#        "feedback.html",
#        usuario=nombre_usuario,
#        feedbackid=feedbackid,
#        by_intent=by_intent
#    )
#
from db import buscar_evaluacion, guardar_evaluacion

@app.route("/feedback/", methods=["GET"])
def feedback_view():

    id_user_moodle = request.args.get("id_user")
    feedbackid = request.args.get("feedbackid")
    nombre_usuario = request.args.get("nombre_usuario") or "Usuario"
    curid = request.args.get("curid")
    user_id = request.args.get("user_id")
    documento_identidad = request.args.get("documento_identidad")

    if not id_user_moodle or not feedbackid:
        return "Faltan parámetros: id_user, feedbackid", 400

    data = get_analysis(feedbackid)
    attempts = data.get("attempts", [])
    user_attempts = [a for a in attempts if str(a.get("userid")) == str(id_user_moodle)]

    if not user_attempts:
        return f"No se encontraron intentos para usuario {id_user_moodle}", 200

    attempts_sorted = sorted(user_attempts, key=lambda x: x.get("timemodified", 0))
    results = []
    intentos_por_usuario = defaultdict(int)

    for attempt in attempts_sorted:
        uid = attempt.get("userid")
        intentos_por_usuario[uid] += 1
        intento_num = intentos_por_usuario[uid]

        ts = attempt.get("timemodified", 0)
        fecha_respuesta = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

        for resp in attempt.get("responses", []):
            pregunta_id = str(resp.get("id"))
            pregunta_text = resp.get("name") or ""
            respuesta_text = (resp.get("rawval") or "").strip()

            existente = buscar_evaluacion(curid, feedbackid, id_user_moodle, pregunta_id)

            if existente:
                eval_result = {
                    "similarity_score": existente["similarity_score"],
                    "level_estimate": existente["nivel_estimado"],
                    "chunks_retrieved": [],
                    "gpt_evaluation": existente["gpt_evaluacion"]  # <- STRING
                }
            else:
                eval_result = evaluar_pregunta_con_contexto(
                    pregunta_text, respuesta_text, pregunta_id
                )

                guardar_evaluacion(
                    curid, feedbackid, id_user_moodle, user_id, documento_identidad,
                    intento_num, pregunta_id, pregunta_text, respuesta_text,
                    eval_result.get("similarity_score"),
                    eval_result.get("level_estimate"),
                    eval_result.get("gpt_evaluation"),
                    fecha_respuesta
                )

            results.append({
                "userid": uid,
                "usuario": nombre_usuario,
                "attempt_id": attempt.get("id"),
                "intento": intento_num,
                "fecha": fecha_respuesta,
                "pregunta_id": pregunta_id,
                "pregunta": pregunta_text,
                "respuesta": respuesta_text,
                "evaluation": eval_result
            })

    # Agrupar por intentos
    by_intent = defaultdict(list)
    for item in results:
        by_intent[item["intento"]].append(item)

    # === Convertir JSON-string a dict antes del template ===
    import json
    for intent_num, items in by_intent.items():
        for item in items:
            gpt_eval = item["evaluation"]["gpt_evaluation"]
            if isinstance(gpt_eval, str):
                try:
                    item["evaluation"]["gpt_evaluation"] = json.loads(gpt_eval)
                except json.JSONDecodeError:
                    pass

    return render_template(
        "feedback.html",
        usuario=nombre_usuario,
        feedbackid=feedbackid,
        by_intent=by_intent
    )



if __name__ == "__main__":
    logging.info("Iniciando Flask app")
    app.run(host="0.0.0.0", port=5000, debug=True)