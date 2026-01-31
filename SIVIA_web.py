import os
import json
import logging
import base64
from datetime import datetime
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
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
# Gemini 1.5 Flash es necesario para herramientas y visión
GENAI_MODEL = "gemini-1.5-flash"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "identidad": """Soy SIVIA (Sistema de Innovación Virtual con Inteligencia Aplicada), una asistente virtual.
Mi personalidad:
- Amigable y empática
- Profesional y clara
- Comprometida con ayudar a cualquier usuario
- Experta en temas generales y tecnológicos
Mi propósito es asistir y responder preguntas de manera útil y confiable.""",
        "memoria_corto_plazo": []
    }

class CognitiveEngine:
    def __init__(self, knowledge):
        self.knowledge = knowledge
        # Se inicializa con la herramienta de búsqueda de Google activa
        self.genai_model = genai.GenerativeModel(
            model_name=GENAI_MODEL,
            tools=[{'google_search': {}}]
        )
        self.chat_session = self.genai_model.start_chat(history=[])
        logging.info(f"Modelo {GENAI_MODEL} cargado con Google Search.")

    def respond(self, text, image_b64=None):
        content_parts = []
        
        # Si hay imagen, se adjunta primero
        if image_b64:
            content_parts.append({
                "mime_type": "image/jpeg",
                "data": image_b64
            })
        
        # Lógica de generación de imágenes (Pollinations)
        text_lower = text.lower()
        if "genera una imagen" in text_lower or "dibuja" in text_lower:
            prompt = text_lower.replace("genera una imagen de", "").replace("dibuja", "").strip()
            url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
            return f"He generado esta imagen para ti: {url}"

        # Prompt con identidad
        full_prompt = f"{self.knowledge['identidad']}\n\nPregunta del usuario: {text}"
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
    print(f"❌ Error crítico: {e}")
    engine = None

@app.route("/chat", methods=['POST'])
def handle_chat():
    global engine
    if not engine:
        return jsonify({"answer": "SIVIA no disponible."}), 500

    user_question = request.json.get("question", "")
    image_data = request.json.get("image") # Viene de sivia.js como base64

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
