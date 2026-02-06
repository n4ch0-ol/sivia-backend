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

# 2. CONFIGURACIÓN MANUAL EXACTA
# Sacado de TU propia lista: 'models/gemini-2.0-flash'
# Este modelo es estable y tiene capa gratuita generosa.
MODEL_NAME = "models/gemini-2.0-flash" 

# Construimos la URL con precisión quirúrgica
# La URL final quedará: .../v1beta/models/gemini-2.0-flash:generateContent
API_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"

print(f"🚀 SIVIA CONSTANTE: Usando {MODEL_NAME}")

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
        print(f"📤 Enviando petición a {MODEL_NAME}...")
        response = requests.post(
            API_URL, 
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            print(f"❌ Error Google: {response.text}")
            return jsonify({"answer": f"Error Google ({response.status_code}): {response.text}"}), 500

        result = response.json()
        
        try:
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except:
            return jsonify({"answer": "Google respondió pero no pude leer el texto."})

    except Exception as e:
        print(f"❌ ERROR INTERNO: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
