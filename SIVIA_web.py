import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64
import sys

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR: Falta API KEY", file=sys.stderr)

genai.configure(api_key=GOOGLE_API_KEY)

# 2. SELECCIÓN DE MODELO A PRUEBA DE BALAS
# Google cambia los nombres a veces. Esta lista prueba el específico, luego el alias, luego el viejo.
POSSIBLE_MODELS = [
    "gemini-1.5-flash-001",  # Nombre técnico exacto (Suele arreglar el 404)
    "gemini-1.5-flash",      # El alias (que te estaba fallando)
    "gemini-pro",            # El modelo 1.0 clásico (El tanque, nunca falla)
    "gemini-1.5-pro-001"     # Versión Pro estable
]

active_model = None
model_name_used = "Desconocido"

# Cargamos datos
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        db_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    db_content = "No hay datos."

SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS ---
{db_content}
REGLA: Responde corto y útil.
"""

print("🔄 Buscando un modelo que funcione...", file=sys.stdout)

for m_name in POSSIBLE_MODELS:
    try:
        print(f"🧪 Probando conexión con: {m_name}...", file=sys.stdout)
        test_model = genai.GenerativeModel(
            model_name=m_name,
            system_instruction=SYSTEM_INSTRUCTION
        )
        # Hacemos una prueba real de "ping"
        response = test_model.generate_content("Hola")
        if response:
            active_model = test_model
            model_name_used = m_name
            print(f"✅ CONECTADO EXITOSAMENTE A: {m_name}", file=sys.stdout)
            break # Si funciona, dejamos de buscar
    except Exception as e:
        print(f"⚠️ {m_name} falló ({e}). Probando el siguiente...", file=sys.stderr)

if not active_model:
    print("❌ ERROR CRÍTICO: Ningún modelo funcionó.", file=sys.stderr)

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - Usando: {model_name_used}"

@app.route('/chat', methods=['POST'])
def chat():
    if not active_model:
        return jsonify({"answer": "Error grave: SIVIA no pudo conectarse a Google."}), 500

    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        if img_data:
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            response = active_model.generate_content([user_msg, img])
        else:
            response = active_model.generate_content(user_msg)

        return jsonify({"answer": response.text})

    except Exception as e:
        print(f"❌ Error en chat: {e}", file=sys.stderr)
        return jsonify({"answer": "Ocurrió un error al procesar tu mensaje."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
