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

# Cache para no buscar el modelo todo el tiempo
CACHED_MODEL_URL = None

# --- DETECTIVE DE MODELOS (Anti-404) ---
def get_working_url():
    global CACHED_MODEL_URL
    if CACHED_MODEL_URL: return CACHED_MODEL_URL

    try:
        response = requests.get(f"{BASE_URL}/models?key={GOOGLE_API_KEY}")
        data = response.json()
        
        if "models" not in data:
            # URL por defecto si falla el listado
            return f"{BASE_URL}/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"

        # Buscamos Gemini 1.5 Flash o Pro
        candidates = [m["name"] for m in data["models"] if "generateContent" in m.get("supportedGenerationMethods", [])]
        logging.info(f"Modelos: {candidates}")

        chosen = None
        for m in candidates:
            if "gemini-1.5-flash" in m: 
                chosen = m; break
        if not chosen: chosen = candidates[0]

        # chosen viene como "models/gemini-..."
        url = f"{BASE_URL}/{chosen}:generateContent?key={GOOGLE_API_KEY}"
        CACHED_MODEL_URL = url
        return url
    except:
        return f"{BASE_URL}/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"

# --- CONOCIMIENTO ---
def load_knowledge():
    filename = "knowledge_base.json"
    base = """ERES SIVIA.
    1. Usa la herramienta de búsqueda para datos actuales.
    2. Respuestas LARGAS y detalladas.
    3. NO Wikipedia.
    4. Usa el JSON para datos internos."""
    
    json_txt = ""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                json_txt = json.dumps(json.load(f), ensure_ascii=False)
        except: pass
    return f"{base}\nDATOS INTERNOS:{json_txt}"

# --- LLAMADA A LA API (Con Fallback) ---
def call_gemini(text, image_b64=None):
    if not GOOGLE_API_KEY: return "Falta API Key."
    
    url = get_working_url()
    headers = {"Content-Type": "application/json"}
    
    # Construcción de partes
    parts = []
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
    parts.append({"text": text})

    system_instr = {"parts": [{"text": load_knowledge()}]}

    # INTENTO 1: CON BÚSQUEDA (Sintaxis Nueva Simplificada)
    payload_with_search = {
        "contents": [{"parts": parts}],
        "system_instruction": system_instr,
        "tools": [
            # ESTO ES LO QUE PEDÍA EL ERROR 400:
            {"google_search": {}} 
        ]
    }

    try:
        logging.info("➡️ Intentando con Google Search...")
        response = requests.post(url, headers=headers, json=payload_with_search)
        
        if response.status_code == 200:
            return parse_response(response.json())
        
        # SI FALLA LA BÚSQUEDA (Error 400 u otro), REINTENTAMOS SIN ELLA
        logging.warning(f"⚠️ Falló búsqueda ({response.status_code}). Reintentando modo simple.")
        
        payload_simple = {
            "contents": [{"parts": parts}],
            "system_instruction": system_instr
            # Sin tools
        }
        
        response_retry = requests.post(url, headers=headers, json=payload_simple)
        if response_retry.status_code == 200:
            return parse_response(response_retry.json()) + "\n(Nota: No pude acceder a internet, te respondo con mi base interna)."
        else:
            return f"Error Final ({response_retry.status_code}): {response_retry.text}"

    except Exception as e:
        return f"Error de conexión: {e}"

def parse_response(data):
    try:
        cand = data['candidates'][0]
        # Verificar si hay texto
        if 'content' in cand and 'parts' in cand['content']:
            return cand['content']['parts'][0]['text']
        # A veces la respuesta está en metadata si solo buscó
        return "He procesado la información pero Google no generó texto. Intenta reformular."
    except:
        return "Respuesta ilegible de Google."

# --- APP ---
app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=['POST'])
def handle_chat():
    data = request.json
    q = data.get("question", "")
    img = data.get("image")
    q_low = q.lower()

    # Multimedia (Pollinations)
    vid_keys = ["genera un video", "crea un video", "haz un video"]
    img_keys = ["genera una imagen", "dibuja", "foto de"]

    if any(k in q_low for k in vid_keys):
        p = q_low
        for k in vid_keys: p = p.replace(k, "")
        url = f"https://image.pollinations.ai/prompt/cinematic%20shot%20{p.strip().replace(' ','%20')}?width=1920&height=1080&nologo=true&model=flux"
        return jsonify({"answer": f"🎥 Concepto: {url}"})

    if any(k in q_low for k in img_keys):
        p = q_low
        for k in img_keys: p = p.replace(k, "")
        url = f"https://image.pollinations.ai/prompt/{p.strip().replace(' ','%20')}?width=1024&height=1024&nologo=true"
        return jsonify({"answer": f"🎨 Imagen: {url}"})

    # Texto
    ans = call_gemini(q, img)
    return jsonify({"answer": ans})

@app.route("/")
def home(): return "SIVIA Online (Retry Mode)"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
