import os
import json
import requests
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR: Falta la API KEY")

# 2. CONFIGURACIÓN DEL MODELO (Hardcoded a Flash)
# Usamos el alias "gemini-1.5-flash" que apunta siempre a la versión estable y GRATUITA.
MODEL_NAME = "gemini-1.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"

print(f"🚀 SIVIA INICIADA. Conectando a: {MODEL_NAME}")

# 3. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Responde de forma útil y breve.
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
        # Construimos el prompt
        full_text = f"{SYSTEM_INSTRUCTION}\n\nUsuario: {user_msg}"
        
        if img_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })
        
        parts.append({"text": full_text})

        payload = {
            "contents": [{"parts": parts}]
        }

        # ENVÍO HTTP
        response = requests.post(
            API_URL, 
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )

        # Si nos pasamos de cuota (429), avisamos amablemente
        if response.status_code == 429:
            return jsonify({"answer": "Estoy saturada de peticiones (Error 429). Espera un minuto."}), 429
            
        if response.status_code != 200:
            return jsonify({"answer": f"Error Google ({response.status_code}): {response.text}"}), 500

        result = response.json()
        
        try:
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except:
            return jsonify({"answer": "Google respondió, pero no entendí el mensaje."})

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
