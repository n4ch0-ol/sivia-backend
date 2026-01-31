import os
import json
import logging
import requests  # <--- Héroe del día
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Configuración
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# URL DIRECTA A LA API (Saltamos la librería)
# Usamos la versión v1beta que es la estándar para Flash hoy en día
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def get_identity():
    """Carga la identidad desde el JSON"""
    prompt = "Eres SIVIA, una asistente virtual útil y profesional."
    if os.path.exists("knowledge_sivia.json"):
        try:
            with open("knowledge_sivia.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("identidad", prompt)
        except: pass
    return prompt

def call_gemini_raw(text, image_b64=None):
    """Hace la petición HTTP directa a Google, sin SDK."""
    
    if not GOOGLE_API_KEY:
        return "❌ Error: Falta la API Key en el servidor."

    headers = {"Content-Type": "application/json"}
    
    # 1. Construcción del Payload (el paquete de datos)
    parts = []
    
    # Si hay imagen, la metemos a mano en el formato que Google pide
    if image_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_b64
            }
        })
    
    # Instrucciones + Texto del usuario
    full_text = f"INSTRUCCIONES DE SISTEMA: {get_identity()}\n\nUSUARIO: {text}"
    parts.append({"text": full_text})
    
    payload = {
        "contents": [{
            "parts": parts
        }]
    }

    # 2. El Envío (Aquí es donde no puede haber error de librería)
    try:
        # Añadimos la key en la URL
        url_final = f"{API_URL}?key={GOOGLE_API_KEY}"
        
        response = requests.post(url_final, headers=headers, json=payload)
        
        # 3. Análisis de la respuesta
        if response.status_code == 200:
            result = response.json()
            # Extraemos el texto de la respuesta JSON compleja de Google
            try:
                return result['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                return "Google respondió pero no entendí el formato. (Respuesta vacía)"
        else:
            # Si Google da error, lo mostramos crudo
            return f"⚠️ Error de Google ({response.status_code}): {response.text}"
            
    except Exception as e:
        return f"Error de conexión HTTP: {str(e)}"

# --- LÓGICA DE SIVIA (Pollinations + Gemini) ---

app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=['POST'])
def handle_chat():
    data = request.json
    if not data: return jsonify({"answer": "Error de datos"}), 400
    
    user_q = data.get("question", "")
    user_img = data.get("image")
    text_lower = user_q.lower()

    # 1. Filtro de Imágenes/Video (Pollinations)
    if "genera" in text_lower or "dibuja" in text_lower or "video" in text_lower:
        prompt = text_lower.replace("genera", "").replace("dibuja", "").replace("un video", "").strip()
        
        if "video" in text_lower:
            url = f"https://image.pollinations.ai/prompt/cinematic%20movie%20scene%20{prompt.replace(' ', '%20')}?width=1920&height=1080&nologo=true&model=flux"
            return jsonify({"answer": f"🎥 Concepto de video generado: {url}"})
        
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
        return jsonify({"answer": f"🎨 Imagen generada: {url}"})

    # 2. Consulta al Cerebro (Vía HTTP Raw)
    respuesta_ai = call_gemini_raw(user_q, user_img)
    return jsonify({"answer": respuesta_ai})

@app.route("/")
def home(): return "SIVIA Backend (Modo HTTP RAW)"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
