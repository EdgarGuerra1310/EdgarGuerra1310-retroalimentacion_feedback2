import requests
import json

TOKEN = "934a5bc65d092299e862902196a6f43b"
DOMAIN = "https://campusvirtual-sifods.minedu.gob.pe"

def get_feedbacks(course_id):
    url = f"{DOMAIN}/webservice/rest/server.php"
    params = {
        "wstoken": TOKEN,
        "wsfunction": "mod_feedback_get_feedbacks_by_courses",
        "moodlewsrestformat": "json",
        "courseids[0]": course_id
    }
    r = requests.get(url, params=params)
    return r.json()

# Llamar a la función
course_id = 1484
feedbacks = get_feedbacks(course_id)

# Guardar en archivo JSON
output_file = f"feedbacks_course_{course_id}.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(feedbacks, f, ensure_ascii=False, indent=4)

print(f"Archivo guardado correctamente: {output_file}")