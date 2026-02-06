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

# 2. FUNCIÓN DE AUTO-DESCUBRIMIENTO (SHERLOCK HOLMES)
# Esta función busca el modelo real y construye la URL perfecta.
def get_dynamic_model_url():
    try:
        print("🕵️  Consultando lista de modelos a Google...")
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_API_KEY}"
        resp = requests.get(list_url)
        
        if resp.status_code != 200:
            print(f"⚠️ Error listando modelos ({resp.status_code}). Usando fallback.")
            return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}", "gemini-1.5-flash (Fallback)"

        data = resp.json()
        models = data.get('models', [])
        
        # Buscamos el mejor candidato
        chosen_model_name = ""
        
        # Prioridad 1: Gemini 1.5 Flash
        for m in models:
            if "gemini" in m['name'] and "1.5" in m['name'] and "flash" in m['name'] and "generateContent" in m['supportedGenerationMethods']:
                chosen_model_name = m['name']
                break
        
        # Prioridad 2: Gemini Pro (si no hay flash)
        if not chosen_model_name:
            for m in models:
                if "gemini" in m['name'] and "pro" in m['name'] and "generateContent" in m['supportedGenerationMethods']:
                    chosen_model_name = m['name']
                    break
        
        # Prioridad 3: El primero que funcione
        if not chosen_model_name and models:
            chosen_model_name = models[0]['name']

        if chosen_model_name:
            print(f"✅ MODELO ENCONTRADO: {chosen_model_name}")
            # TRUCO: El nombre ya viene como 'models/gemini-xyz'.
            # La URL base es 'https://generativelanguage.googleapis.com/v1beta/'
            # Solo concatenamos. NO agregamos 'models/' extra.
            final_url = f"https://generativelanguage.googleapis.com/v1beta/{chosen_model_name}:generateContent?key={GOOGLE_API_KEY}"
            return final_url, chosen_model_name
        else:
            print("⚠️ No se encontraron modelos compatibles.")
            return None, "Ninguno"

    except Exception as e:
        print(f"❌ Error en autodetección: {e}")
        return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}", "gemini-1.5-flash (Error)"

# INICIALIZAMOS LA URL AL ARRANCAR
ACTIVE_URL, MODEL_NAME_DISPLAY = get_dynamic_model_url()

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
REGLA: Responde de forma útil.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - Usando: {MODEL_NAME_DISPLAY}"

@app.route('/chat', methods=['POST'])
def chat():
    # Si por alguna razón la URL no se generó al inicio, intentamos de nuevo
    global ACTIVE_URL
    if not ACTIVE_URL:
        ACTIVE_URL, _ = get_dynamic_model_url()

    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        parts = []
        # Prompt + Sistema
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
            ACTIVE_URL, 
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"answer": f"Error Google ({response.status_code}): {response.text}"}), 500

        result = response.json()
        
        # Extracción segura
        try:
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except:
            return jsonify({"answer": "No pude leer la respuesta de Google."})

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
