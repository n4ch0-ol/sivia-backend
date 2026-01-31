import os
import json
import logging
import base64
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

KNOWLEDGE_FILE = "knowledge_sivia.json"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("❌ No se encontró la GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)

# MODELO ESTABLE
GENAI_MODEL = "gemini-1.5-flash"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"identidad": "Soy SIVIA, tu asistente virtual."}

class CognitiveEngine:
    def __init__(self, knowledge):
        self.knowledge = knowledge
        # CARGA DIRECTA SIN TOOLS (Evita el error 404 de la v1beta)
        try:
            self.genai_model = genai.GenerativeModel(model_name=GENAI_MODEL)
            self.chat_session = self.genai_model.start_chat(history=[])
            logging.info(f"✅ SIVIA ONLINE con {GENAI_MODEL}")
        except Exception as e:
            logging.error(f"❌ Error fatal: {e}")
            self.genai_model = None

    def respond(self, text, image_b64=None):
        if not self.genai_model: return "Servicio no disponible."
        
        content_parts = []
        
        # Si hay imagen (Base64), la procesamos
        if image_b64:
            content_parts.append({"mime_type": "image/jpeg", "data": image_b64})
        
        # Lógica de imágenes Pollinations
        text_lower = text.lower() if text else ""
        if "genera una imagen" in text_lower or "dibuja" in text_lower:
            p = text_lower.replace("genera una imagen de", "").replace("dibuja", "").strip()
            url = f"https://image.pollinations.ai/prompt/{p.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
            return f"He generado esta imagen para ti: {url}"

        # Prompt con identidad
        full_prompt = f"{self.knowledge.get('identidad', '')}\n\nUsuario: {text}"
        content_parts.append(full_prompt)

        try:
            response = self.chat_session.send_message(content_parts)
            return response.text
        except Exception as e:
            logging.error(f"Error Gemini: {e}")
            return "Lo siento, hubo un error. Intentá de nuevo."

app = Flask(__name__)
CORS(app)

kb = load_knowledge()
engine = CognitiveEngine(kb)

@app.route("/chat", methods=['POST'])
def handle_chat():
    if not engine: return jsonify({"answer": "SIVIA offline"}), 500
    data = request.json
    try:
        ans = engine.respond(data.get("question", ""), data.get("image"))
        return jsonify({"answer": ans})
    except:
        return jsonify({"answer": "Error"}), 500

@app.route("/")
def hello(): return "SIVIA OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
