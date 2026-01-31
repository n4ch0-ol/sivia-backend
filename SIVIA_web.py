import os
import json
import logging
import base64
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Configuración inicial
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

KNOWLEDGE_FILE = "knowledge_sivia.json"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("❌ No se encontró la GOOGLE_API_KEY en las variables de entorno.")

genai.configure(api_key=GOOGLE_API_KEY)
# Usamos el nombre estable para máxima compatibilidad
GENAI_MODEL = "gemini-1.5-flash"

def load_knowledge():
    """Carga la base de conocimientos desde el archivo JSON local."""
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error cargando JSON: {e}")
    
    # Valores por defecto si el archivo no existe o falla
    return {
        "identidad": "Soy SIVIA (Sistema de Innovación Virtual con Inteligencia Aplicada), tu asistente virtual profesional y empática.",
        "memoria_corto_plazo": []
    }

class CognitiveEngine:
    def __init__(self, knowledge):
        self.knowledge = knowledge
        try:
            # Intento de inicialización con Búsqueda Web (Deep Research)
            self.genai_model = genai.GenerativeModel(
                model_name=GENAI_MODEL,
                tools=[{"google_search_retrieval": {}}]
            )
            self.chat_session = self.genai_model.start_chat(history=[])
            logging.info(f"✅ SIVIA lista con {GENAI_MODEL} y Google Search.")
        except Exception as e:
            logging.warning(f"⚠️ Falló Google Search, activando modo estándar: {e}")
            # Fallback: Inicia sin herramientas si la API Key no soporta v1beta/search
            self.genai_model = genai.GenerativeModel(model_name=GENAI_MODEL)
            self.chat_session = self.genai_model.start_chat(history=[])

    def respond(self, text, image_b64=None):
        content_parts = []
        
        # 1. Soporte para Visión (Multimodalidad)
        if image_b64:
            content_parts.append({
                "mime_type": "image/jpeg",
                "data": image_b64
            })
        
        # 2. Lógica de generación de imágenes (Pollinations)
        text_lower = text.lower() if text else ""
        if "genera una imagen" in text_lower or "dibuja" in text_lower:
            prompt = text_lower.replace("genera una imagen de", "").replace("dibuja", "").strip()
            if not prompt: prompt = "un paisaje futurista"
            url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
            return f"He generado esta imagen para ti: {url}"

        # 3. Construcción del Prompt con Identidad
        identidad = self.knowledge.get('identidad', '')
        full_prompt = f"{identidad}\n\nPregunta del usuario: {text}"
        content_parts.append(full_prompt)

        try:
            response = self.chat_session.send_message(content_parts)
            return response.text
        except Exception as e:
            logging.error(f"Error en Gemini: {e}")
            return "Lo siento, tuve un problema al procesar eso. ¿Podrías intentar de nuevo?"

# --- Configuración Flask ---

app = Flask(__name__)
CORS(app)

# Inicialización del motor global
try:
    kb = load_knowledge()
    engine = CognitiveEngine(kb)
except Exception as e:
    logging.critical(f"❌ Error fatal al iniciar SIVIA: {e}")
    engine = None

@app.route("/chat", methods=['POST'])
def handle_chat():
    global engine
    if not engine:
        return jsonify({"answer": "SIVIA no está disponible en este momento."}), 500

    data = request.json
    user_question = data.get("question", "")
    image_data = data.get("image") # Base64 string

    try:
        response_text = engine.respond(user_question, image_data)
        return jsonify({"answer": response_text})
    except Exception as e:
        logging.error(f"Error en ruta /chat: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

@app.route("/")
def health_check():
    return "SIVIA Backend Online", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
