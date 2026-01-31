import os
import json
import logging
import base64
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

KNOWLEDGE_FILE = "knowledge_sivia.json"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
if not GOOGLE_API_KEY:
    raise ValueError("❌ No se encontró la GOOGLE_API_KEY en las variables de entorno.")

genai.configure(api_key=GOOGLE_API_KEY)
GENAI_MODEL = "gemini-1.5-flash-latest"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "identidad": """Soy SIVIA (Sistema de Innovación Virtual con Inteligencia Aplicada), una asistente virtual.
Mi personalidad: amigable, profesional y experta. Ayudo con temas generales y del centro de estudiantes.""",
        "memoria_corto_plazo": []
    }

class CognitiveEngine:
    def __init__(self, knowledge):
        self.knowledge = knowledge
        
        # Usamos la sintaxis de diccionario directo para evitar errores de nombres
        try:
            self.genai_model = genai.GenerativeModel(
                model_name=GENAI_MODEL,
                tools=[{"google_search_retrieval": {}}] 
            )
            self.chat_session = self.genai_model.start_chat(history=[])
            logging.info(f"✅ SIVIA lista y conectada a Google Search.")
        except Exception as e:
            logging.error(f"❌ Error al inicializar el modelo: {e}")
            # Si falla la búsqueda, intentamos cargar el modelo básico para que al menos responda
            self.genai_model = genai.GenerativeModel(model_name=GENAI_MODEL)
            self.chat_session = self.genai_model.start_chat(history=[])

    def respond(self, text, image_b64=None):
        content_parts = []
        
        if image_b64:
            content_parts.append({
                "mime_type": "image/jpeg",
                "data": image_b64
            })
        
        text_lower = text.lower()
        if "genera una imagen" in text_lower or "dibuja" in text_lower:
            prompt = text_lower.replace("genera una imagen de", "").replace("dibuja", "").strip()
            url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
            return f"He generado esta imagen para ti: {url}"

        full_prompt = f"{self.knowledge.get('identidad', '')}\n\nPregunta del usuario: {text}"
        content_parts.append(full_prompt)

        try:
            response = self.chat_session.send_message(content_parts)
            return response.text
        except Exception as e:
            logging.error(f"Error en Gemini: {e}")
            return "Lo siento, tuve un problema al procesar eso."

app = Flask(__name__)
CORS(app) 

try:
    kb = load_knowledge()
    engine = CognitiveEngine(kb)
except Exception as e:
    logging.critical(f"❌ Error crítico al iniciar SIVIA: {e}")
    engine = None

@app.route("/chat", methods=['POST'])
def handle_chat():
    global engine
    if not engine:
        return jsonify({"answer": "SIVIA no disponible."}), 500

    user_question = request.json.get("question", "")
    image_data = request.json.get("image")

    try:
        response_text = engine.respond(user_question, image_data)
        return jsonify({"answer": response_text})
    except Exception as e:
        return jsonify({"answer": "Error procesando la respuesta."}), 500

@app.route("/")
def hello():
    return "SIVIA Backend Online"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)





