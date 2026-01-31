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
# URL de la API v1beta (Necesaria para herramientas de búsqueda)
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"

# --- GESTOR DE CONOCIMIENTO (JSON) ---
def load_knowledge():
    """Carga knowledge_base.json y construye el prompt del sistema."""
    filename = "knowledge_base.json"
    
    # Identidad Base
    base_prompt = """
    ERES SIVIA (Sistema de Innovación Virtual con Inteligencia Aplicada).
    
    TUS REGLAS DE ORO:
    1. Eres la asistente oficial de la organización.
    2. Tienes acceso a Búsqueda Web: Úsala SIEMPRE que te pregunten datos actuales (clima, noticias, fechas).
    3. Tus respuestas deben ser EXTENSAS, detalladas y útiles. No seas escueta.
    4. NO uses Wikipedia. Busca en sitios .edu, .org, .gob o noticias reputadas.
    5. Si te preguntan quién eres, usa la información del JSON adjunto.
    """
    
    json_content = ""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                json_content = json.dumps(data, ensure_ascii=False, indent=2)
                logging.info(f"✅ JSON Cargado: {filename}")
        except Exception as e:
            logging.error(f"❌ Error leyendo JSON: {e}")
            json_content = "No se pudo leer la base de datos local."
    else:
        logging.warning(f"⚠️ Archivo {filename} no encontrado en la raíz.")

    return f"{base_prompt}\n\n=== BASE DE CONOCIMIENTO INTERNA ===\n{json_content}"

# --- MOTOR HTTP RAW (Sin Librería Google) ---
def call_gemini_advanced(user_text, image_b64=None):
    if not GOOGLE_API_KEY: return "❌ Error: Falta API Key."

    headers = {"Content-Type": "application/json"}
    
    # 1. Contenido (Texto + Imagen opcional)
    parts = []
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
    
    parts.append({"text": user_text})

    # 2. Payload con SEARCH activado correctamente
    payload = {
        "contents": [{
            "parts": parts
        }],
        "system_instruction": {
            "parts": [{"text": load_knowledge()}]
        },
        "tools": [
            {
                "googleSearchRetrieval": {
                    "dynamicRetrievalConfig": {
                        # AQUÍ ESTABA EL ERROR: Debe ser MODE_DYNAMIC en mayúsculas
                        "mode": "MODE_DYNAMIC", 
                        "dynamicThreshold": 0.6
                    }
                }
            }
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            # Intentamos extraer el texto
            try:
                # A veces Google devuelve varias partes, las unimos
                candidates = data.get('candidates', [])
                if not candidates:
                    return "El modelo recibió la solicitud pero no generó texto (quizás solo buscó internamente)."
                
                parts_response = candidates[0]['content']['parts']
                final_text = ""
                for p in parts_response:
                    if 'text' in p:
                        final_text += p['text']
                
                return final_text if final_text else "Respuesta vacía del modelo."
                
            except Exception as e:
                logging.error(f"Error parseando JSON: {data}")
                return "Error procesando la respuesta de Google."
        else:
            return f"⚠️ Error Google ({response.status_code}): {response.text}"

    except Exception as e:
        return f"Error de conexión: {str(e)}"

# --- APP FLASK ---
app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=['POST'])
def handle_chat():
    data = request.json
    if not data: return jsonify({"answer": "Error: Sin datos"}), 400
    
    q = data.get("question", "")
    img = data.get("image")
    text_lower = q.lower()

    # --- GENERACIÓN DE IMAGEN/VIDEO (Pollinations) ---
    vid_keys = ["genera un video", "crea un video", "haz un video", "video de"]
    img_keys = ["genera una imagen", "dibuja", "foto de", "crea una imagen"]

    # Video (Simulado)
    if any(k in text_lower for k in vid_keys):
        prompt = text_lower
        for k in vid_keys: prompt = prompt.replace(k, "")
        url = f"https://image.pollinations.ai/prompt/cinematic%20shot%20{prompt.strip().replace(' ','%20')}?width=1920&height=1080&nologo=true&model=flux"
        return jsonify({"answer": f"🎥 Concepto de video generado: {url}"})

    # Imagen
    if any(k in text_lower for k in img_keys):
        prompt = text_lower
        for k in img_keys: prompt = prompt.replace(k, "")
        url = f"https://image.pollinations.ai/prompt/{prompt.strip().replace(' ','%20')}?width=1024&height=1024&nologo=true"
        return jsonify({"answer": f"🎨 Imagen generada: {url}"})

    # Respuesta Inteligente
    respuesta = call_gemini_advanced(q, img)
    return jsonify({"answer": respuesta})

@app.route("/")
def home(): return "SIVIA Backend (HTTP + Search Fix) Online"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
