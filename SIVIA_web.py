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

# 2. CONFIGURACIÓN "A MANO" (SIN LIBRERÍA GOOGLE)
# Usamos la API v1b (versión estable) y el modelo Flash que es el más permisivo.
# Si este falla, el problema es tu API KEY (créditos/bloqueo).
MODEL_NAME = "gemini-1.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"

print(f"🚀 SIVIA INICIANDO EN MODO HTTP DIRECTO ({MODEL_NAME})")

# 3. BASE DE DATOS
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
    if not GOOGLE_API_KEY:
        return "ERROR: FALTA API KEY"
    return f"SIVIA HTTP MODE - ONLINE"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        # Construcción manual del paquete JSON para Google
        parts = []
        full_prompt = f"{SYSTEM_INSTRUCTION}\n\nUsuario: {user_msg}"

        if img_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })
        
        parts.append({"text": full_prompt})

        payload = {
            "contents": [{"parts": parts}]
        }

        # ENVÍO DIRECTO (Sin intermediarios)
        print(f"📡 Enviando petición a Google...")
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )

        # MANEJO DE ERRORES REAL
        if response.status_code != 200:
            error_details = response.text
            print(f"❌ ERROR GOOGLE ({response.status_code}): {error_details}")
            
            # Si es error 429 (Cuota), avisamos bonito
            if response.status_code == 429:
                return jsonify({"answer": "Estoy saturada (Límite de cuota Google). Intenta en un rato."})
            
            # Si es 404 (Modelo no existe/mal nombre)
            if response.status_code == 404:
                return jsonify({"answer": "Error de configuración: Google no encuentra el modelo 1.5-flash."})

            return jsonify({"answer": f"Error técnico ({response.status_code}): {error_details}"})

        # PROCESAR RESPUESTA
        result = response.json()
        try:
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except (KeyError, IndexError):
            # A veces Google devuelve respuesta vacía si bloquea por seguridad
            return jsonify({"answer": "Google bloqueó la respuesta (Seguridad/Filtro)."})

    except Exception as e:
        print(f"❌ ERROR SERVIDOR: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
