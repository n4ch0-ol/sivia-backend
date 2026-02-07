import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- AQUÍ ESTÁ EL CAMBIO ---
# Usamos el nombre que VIMOS en tu lista de modelos disponibles.
# 'gemini-flash-latest' apunta siempre a la versión Flash más nueva que tengas habilitada.
MODEL_NAME = "gemini-flash-latest" 

API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"

print(f"🚀 SIVIA CONECTANDO A: {MODEL_NAME}")

try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos."

SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS ---
{database_content}
Responde corto y útil.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        parts = []
        # Prompt del sistema + usuario
        parts.append({"text": f"{SYSTEM_INSTRUCTION}\n\nUsuario: {user_msg}"})

        if img_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })

        payload = {"contents": [{"parts": parts}]}

        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            # Si falla, imprimimos el error EXACTO de Google
            print(f"❌ ERROR GOOGLE: {response.text}")
            return jsonify({"answer": f"Error Google ({response.status_code}): {response.text}"}), response.status_code

        result = response.json()
        try:
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except:
            return jsonify({"answer": "Google respondió vacío."})

    except Exception as e:
        print(f"❌ ERROR INTERNO: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
