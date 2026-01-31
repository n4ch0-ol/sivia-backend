import os
import json
import logging
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# VARIABLE GLOBAL PARA GUARDAR EL MODELO QUE FUNCIONA
CACHED_MODEL_NAME = None

def get_best_model():
    """Pregunta a Google qué modelos hay y elige el mejor disponible."""
    global CACHED_MODEL_NAME
    if CACHED_MODEL_NAME: return CACHED_MODEL_NAME

    try:
        url = f"{BASE_URL}/models?key={GOOGLE_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if "models" not in data:
            logging.error(f"Error listando modelos: {data}")
            return "models/gemini-1.5-flash" # Intento desesperado por defecto

        # Buscamos modelos que sirvan para generar contenido
        candidates = []
        for m in data["models"]:
            if "generateContent" in m.get("supportedGenerationMethods", []):
                candidates.append(m["name"])
        
        logging.info(f"Modelos disponibles en tu cuenta: {candidates}")

        # Prioridad: Flash -> Pro -> Cualquiera
        chosen = None
        for c in candidates:
            if "flash" in c and "1.5" in c:
                chosen = c
                break
        if not chosen:
            for c in candidates:
                if "gemini-1.5" in c:
                    chosen = c
                    break
        if not chosen and candidates:
            chosen = candidates[0]

        logging.info(f"🏆 MODELO ELEGIDO AUTOMÁTICAMENTE: {chosen}")
        CACHED_MODEL_NAME = chosen
        return chosen

    except Exception as e:
        logging.error(f"Fallo al buscar modelos: {e}")
        return "models/gemini-1.5-flash"

def call_gemini_dynamic(text, image_b64=None):
    if not GOOGLE_API_KEY: return "❌ Falta API Key."
    
    # 1. Obtenemos el nombre REAL del modelo
    model_name = get_best_model()
    
    # 2. Construimos la URL con ese nombre confirmado
    # Nota: model_name ya viene como 'models/gemini-xB', así que cuidado con la URL
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
        
    api_url = f"{BASE_URL}/{model_name}:generateContent?key={GOOGLE_API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    parts = []
    
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
    
    # Identidad
    identidad = "Eres SIVIA, asistente virtual eficiente. No uses Wikipedia."
    full_text = f"SISTEMA: {identidad}\nUSUARIO: {text}"
    parts.append({"text": full_text})
    
    payload = {"contents": [{"parts": parts}]}

    try:
        response = requests.post(api_url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # Si falla, reseteamos el caché por si el modelo murió
            global CACHED_MODEL_NAME
            CACHED_MODEL_NAME = None
            return f"⚠️ Error Google ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Error conexión: {str(e)}"

# --- APP ---
app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=['POST'])
def chat():
    data = request.json
    q = data.get("question", "")
    img = data.get("image")
    
    # Pollinations
    text_lower = q.lower()
    if "genera" in text_lower or "dibuja" in text_lower or "video" in text_lower:
        prompt = text_lower.replace("genera", "").replace("dibuja", "").replace("un video", "").strip()
        if "video" in text_lower:
             url = f"https://image.pollinations.ai/prompt/cinematic%20{prompt.replace(' ','%20')}?width=1920&height=1080&nologo=true&model=flux"
             return jsonify({"answer": f"🎥 Concepto: {url}"})
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ','%20')}?width=1024&height=1024&nologo=true"
        return jsonify({"answer": f"🎨 Imagen: {url}"})

    # Gemini Auto-detect
    ans = call_gemini_dynamic(q, img)
    return jsonify({"answer": ans})

@app.route("/")
def home(): 
    return "SIVIA Auto-Healing Online"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
