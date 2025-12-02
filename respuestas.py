import requests
import json

TOKEN = "934a5bc65d092299e862902196a6f43b"
DOMAIN = "https://campusvirtual-sifods.minedu.gob.pe"

def call(function, params):
    url = f"{DOMAIN}/webservice/rest/server.php"
    base_params = {
        "wstoken": TOKEN,
        "wsfunction": function,
        "moodlewsrestformat": "json",
    }
    base_params.update(params)
    r = requests.get(url, params=base_params)
    return r.json()

# 1. OBTENER FEEDBACKS DEL CURSO
def get_feedbacks(course_id):
    return call("mod_feedback_get_feedbacks_by_courses", {"courseids[0]": course_id})

# 2. OBTENER PREGUNTAS DE UN FEEDBACK
def get_feedback_questions(feedback_id):
    return call("mod_feedback_get_items", {"feedbackid": feedback_id})

# 3. OBTENER RESPUESTAS DE LOS USUARIOS
def get_feedback_responses(feedback_id):
    return call("mod_feedback_get_responses_analysis", {"feedbackid": feedback_id})

# ---------- MAIN WORKFLOW ----------
course_id = 1484

# Obtener feedbacks del curso
feedbacks = get_feedbacks(course_id)

output = {
    "course_id": course_id,
    "feedbacks": []
}

for fb in feedbacks.get("feedbacks", []):
    fb_id = fb["id"]

    preguntas = get_feedback_questions(fb_id)
    respuestas = get_feedback_responses(fb_id)

    output["feedbacks"].append({
        "feedback_id": fb_id,
        "feedback_name": fb["name"],
        "questions": preguntas,
        "responses": respuestas
    })

# Guardar todo en JSON
with open("feedback_full_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("Todo guardado en feedback_full_data.json")