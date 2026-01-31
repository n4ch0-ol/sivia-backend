import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# 1. Configuración Básica
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# 2. Clave de API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logging.warning("⚠️ Sin API KEY. SIVIA no responderá preguntas complejas.")
else:
    genai.configure(api_key=GOOGLE_API_KEY)

# 3. Carga de Identidad (JSON)
def get_system_prompt():
    base_prompt = """Eres SIVIA. 
    - Eres útil, directa y profesional.
    - NO uses Wikipedia. Busca fuentes confiables (.edu, .org).
    - Si te piden video, genera un concepto visual."""
    
    if os.path.exists("knowledge_sivia.json"):
        try:
            with open("knowledge_sivia.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("identidad", base_prompt)
        except: pass
    return base_prompt

# 4. Motor Cognitivo (Modo Directo - Sin Sesión)
def generate_response(user_text, image_b64=None):
    # A. Filtro de Imágenes/Video (Pollinations)
    text_lower = user_text.lower()
    if "genera" in text_lower or "dibuja" in text_lower or "video" in text_lower:
        prompt = text_lower.replace("genera", "").replace("dibuja", "").replace("un video", "").strip()
        
        # Truco para "Video": Imagen formato cine (16:9)
        if "video" in text_lower:
            url = f"https://image.pollinations.ai/prompt/cinematic%20shot%20{prompt.replace(' ', '%20')}?width=1920&height=1080&nologo=true&model=flux"
            return f"🎬 He creado este concepto visual para tu video: {url}"
        
        # Imagen normal
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
        return f"🎨 Aquí tienes: {url}"

    # B. Preparar el mensaje para Google
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        content = []
        
        # 1. Si hay imagen adjunta (Visión)
        if image_b64:
            content.append({"mime_type": "image/jpeg", "data": image_b64})
        
        # 2. Instrucciones + Pregunta (Simulamos memoria enviando todo junto)
        system_instruction = get_system_prompt()
        full_prompt = f"INSTRUCCIONES DEL SISTEMA:\n{system_instruction}\n\nPREGUNTA DEL USUARIO:\n{user_text}"
        content.append(full_prompt)

        # 3. Generación DIRECTA (Esto evita el error de conexión de sesión)
        response = model.generate_content(content)
        return response.text

    except Exception as e:
        logging.error(f"❌ Error Gemini: {e}")
        return "⚠️ Error de conexión. Por favor, regenera tu API Key o intenta en 1 min."

# --- SERVIDOR FLASK ---
app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=['POST'])
def chat():
    data = request.json
    try:
        respuesta = generate_response(data.get("question", ""), data.get("image"))
        return jsonify({"answer": respuesta})
    except Exception as e:
        return jsonify({"answer": "Error interno del servidor."}), 500

@app.route("/")
def home(): return "SIVIA Online (Modo Stateless)"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
