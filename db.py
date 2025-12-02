import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

# Buscar si ya existe evaluación
def buscar_evaluacion(curid, feedbackid, id_user_moodle, pregunta_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT * FROM evaluaciones_feedback
        WHERE curid = %s AND feedback_id = %s
          AND id_user_moodle = %s AND pregunta_id = %s
        ORDER BY fecha_retroalimentacion DESC LIMIT 1
    """, (curid, feedbackid, id_user_moodle, pregunta_id))

    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

# Insertar nueva evaluación
def guardar_evaluacion(
    curid, feedbackid, id_user_moodle, user_id, documento_identidad,
    intento, pregunta_id, pregunta, respuesta,
    similarity_score, nivel_estimado, gpt_evaluacion, fecha_respuesta
):
    conn = get_db_connection()
    cur = conn.cursor()

    # Convertir dict a JSON si corresponde
    if isinstance(gpt_evaluacion, dict):
        gpt_evaluacion = json.dumps(gpt_evaluacion, ensure_ascii=False)

    cur.execute("""
        INSERT INTO evaluaciones_feedback
        (curid, feedback_id, id_user_moodle, user_id, documento_identidad,
         intento, pregunta_id, pregunta, respuesta,
         similarity_score, nivel_estimado, gpt_evaluacion,
         fecha_respuesta)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        curid, feedbackid, id_user_moodle, user_id, documento_identidad,
        intento, pregunta_id, pregunta, respuesta,
        similarity_score, nivel_estimado, gpt_evaluacion, fecha_respuesta
    ))

    conn.commit()
    cur.close()
    conn.close()