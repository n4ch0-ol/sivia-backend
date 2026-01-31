import os
import json
import logging
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Variable para no preguntar el nombre del modelo en cada mensaje
CACHED_MODEL_URL = None

# --- PASO 1: DETECTIVE DE MODELOS ---
def get_working_url():
    """Pregunta a Google qué modelo existe realmente y devuelve la URL completa."""
    global CACHED_MODEL_URL
    if CACHED_MODEL_URL: return CACHED_MODEL_URL

    try:
        logging.info("🕵️ Buscando modelos disponibles en tu cuenta...")
        response = requests.get(f"{BASE_URL}/models?key={GOOGLE_API_KEY}")
        data = response.json()
        
        if "models" not in data:
            logging.error(f"Error listando modelos: {data}")
            # Fallback desesperado
            return f"{BASE_URL}/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"

        # Filtramos modelos que generen contenido
        candidates = [m["name"] for m in data["models"] if "generateContent" in m.get("supportedGenerationMethods", [])]
        
        logging.info(f"📋 Modelos encontrados: {candidates}")

        # Lógica de selección: Preferimos Flash 1.5 -> Flash -> Pro -> El primero que haya
        chosen_model = None
        for m in candidates:
            if "gemini-1.5-flash" in m: 
                chosen_model = m
                break
        if not chosen_model:
            for m in candidates:
                if "gemini-1.5" in m:
                    chosen_model = m
                    break
        if not chosen_model and candidates:
            chosen_model = candidates[0]

        if not chosen_model:
            raise Exception("No se encontraron modelos compatibles.")

        # Construimos la URL final
        # Nota: 'chosen_model' ya viene con el prefijo "models/", ej: "models/gemini-1.5-flash-001"
        final_url = f"{BASE_URL}/{chosen_model}:generateContent?key={GOOGLE_API_KEY}"
        
        logging.info(f"🎯 MODELO SELECCIONADO: {chosen_model}")
        CACHED_MODEL_URL = final_url
        return final_url

    except Exception as e:
        logging.error(f"Error fatal buscando modelos: {e}")
        return f"{BASE_URL}/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"

# --- PASO 2: CONOCIMIENTO ---
def load_knowledge():
    filename = "knowledge_base.json"
    base_prompt = """
    ERES SIVIA.
    1. Usa la Búsqueda de Google (tools) para datos actuales.
    2. Tus respuestas deben ser EXTENSAS y COMPLETAS.
    3. NO uses Wikipedia.
    4. Si preguntan quién eres, usa el JSON adjunto.
    """
    json_content = ""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                json_content = json.dumps(data, ensure_ascii=False)
        except: pass
    
    return f"{base_prompt}\nDATA:{json_content}"

# --- PASO 3: LLAMADA A LA API ---
def call_gemini(text, image_b64=None):
    if not GOOGLE_API_KEY: return "Error: Sin API Key."
    
    # Obtenemos la URL dinámica
    url = get_working_url()
    
    headers = {"Content-Type": "application/json"}
    parts = []
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
    parts.append({"text": text})

    payload = {
        "contents": [{"parts": parts}],
        "system_instruction": {"parts": [{"text": load_knowledge()}]},
        # CONFIGURACIÓN DE BÚSQUEDA WEB (CORREGIDA)
        "tools": [{
            "googleSearchRetrieval": {
                "dynamicRetrievalConfig": {
                    "mode": "MODE_DYNAMIC", 
                    "dynamicThreshold": 0.6
                }
            }
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            try:
                # Extracción robusta de texto
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            except:
                return "Google respondió pero no generó texto (posiblemente solo buscó)."
        else:
            # Si falla, borramos caché por si el modelo cambió
            global CACHED_MODEL_URL
            CACHED_MODEL_URL = None
            return f"⚠️ Error Google ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Error conexión: {e}"

# --- PASO 4: APP FLASK ---
app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=['POST'])
def handle_chat():
    data = request.json
    q = data.get("question", "")
    img = data.get("image")
    text_lower = q.lower()

    # Imágenes / Video
    vid_keys = ["genera un video", "crea un video", "haz un video"]
    img_keys = ["genera una imagen", "dibuja", "foto de"]

    if any(k in text_lower for k in vid_keys):
        p = text_lower
        for k in vid_keys: p = p.replace(k, "")
        url = f"https://image.pollinations.ai/prompt/cinematic%20shot%20{p.strip().replace(' ','%20')}?width=1920&height=1080&nologo=true&model=flux"
        return jsonify({"answer": f"🎥 Concepto de video: {url}"})

    if any(k in text_lower for k in img_keys):
        p = text_lower
        for k in img_keys: p = p.replace(k, "")
        url = f"https://image.pollinations.ai/prompt/{p.strip().replace(' ','%20')}?width=1024&height=1024&nologo=true"
        return jsonify({"answer": f"🎨 Imagen: {url}"})

    # Chat Inteligente
    ans = call_gemini(q, img)
    return jsonify({"answer": ans})

@app.route("/")
def home(): return "SIVIA Auto-Detect Online"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
