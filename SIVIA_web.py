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

# 2. FUNCIÓN PARA ENCONTRAR EL MODELO CORRECTO (SIN ADIVINAR)
def get_working_model_url():
    if not GOOGLE_API_KEY:
        print("❌ ERROR: No hay API Key.")
        return None, "Sin API Key"

    print("🕵️  Preguntando a Google qué modelos tengo disponibles...")
    try:
        # Pedimos la lista a Google
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_API_KEY}"
        resp = requests.get(list_url)
        
        if resp.status_code != 200:
            print(f"⚠️ Error al listar modelos: {resp.status_code}")
            # Fallback de emergencia a la versión 001 específica (suele ser la más segura)
            return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-001:generateContent?key={GOOGLE_API_KEY}", "gemini-1.5-flash-001 (Fallback)"

        data = resp.json()
        models = data.get('models', [])
        
        found_model = None
        
        # BUSCAMOS EL ELEGIDO
        print(f"📋 Modelos encontrados: {[m['name'] for m in models]}") # Esto saldrá en el log
        
        # Prioridad 1: Cualquier variante de Flash (Es rápido y gratis)
        for m in models:
            name = m['name']
            if 'flash' in name.lower():
                found_model = name
                break
        
        # Prioridad 2: Gemini Pro 1.0 (El clásico, también gratis)
        if not found_model:
            for m in models:
                if 'gemini-pro' in name.lower() and '1.5' not in name: # Evitar 1.5 Pro que a veces es de pago
                    found_model = name
                    break
        
        # Prioridad 3: Gemini 1.0 Pro Latest
        if not found_model:
             for m in models:
                if 'gemini-1.0-pro' in name.lower():
                    found_model = name
                    break

        if found_model:
            print(f"✅ ¡EUREKA! Usaremos: {found_model}")
            # Construimos la URL sin duplicar 'models/'
            # La API devuelve 'models/gemini-xyz', así que lo pegamos directo.
            return f"https://generativelanguage.googleapis.com/v1beta/{found_model}:generateContent?key={GOOGLE_API_KEY}", found_model
        else:
            print("⚠️ No encontré ni Flash ni Pro. Probando suerte con gemini-1.5-flash-001 hardcoded.")
            return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-001:generateContent?key={GOOGLE_API_KEY}", "gemini-1.5-flash-001 (Hardcoded)"

    except Exception as e:
        print(f"❌ Error buscando modelos: {e}")
        return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}", "Error"

# INICIALIZACIÓN
ACTIVE_URL, MODEL_NAME = get_working_model_url()

# 3. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos."

SYSTEM_INSTRUCTION = f"""
Eres SIVIA.
--- DATOS ---
{database_content}
Responde breve y útil.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - Model: {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    # Reintentar URL si falló al inicio
    global ACTIVE_URL
    if not ACTIVE_URL or "Error" in MODEL_NAME:
         ACTIVE_URL, _ = get_working_model_url()

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

        payload = {"contents": [{"parts": parts}]}

        print(f"📤 Enviando a: {ACTIVE_URL.split('?')[0]}") # Log para ver a dónde dispara
        
        response = requests.post(
            ACTIVE_URL, 
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"answer": f"Error Google ({response.status_code}): {response.text}"}), 500

        result = response.json()
        try:
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except:
            return jsonify({"answer": "Google respondió vacío."})

    except Exception as e:
        print(f"❌ ERROR SERVER: {e}")
        return jsonify({"answer": "Error interno."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
