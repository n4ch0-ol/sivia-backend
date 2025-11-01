import os
import json
import logging
from datetime import datetime
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# --- NUEVAS LIBRERÍAS PARA EL "WALKIE-TALKIE" ---
from flask import Flask, request, jsonify
from flask_cors import CORS
# -----------------------------------------------

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

KNOWLEDGE_FILE = "knowledge_sivia.json"
TRUSTED_DOMAINS = [".org", ".gob", ".ong", ".gov", ".edu", ".ac."]
SIVIA_IDENTITY = """
Soy SIVIA (Sistema de Innovación Virtual con Inteligencia Aplicada), una asistente virtual.
Mi personalidad:
- Amigable y empática
- Profesional y clara
- Comprometida con ayudar a cualquier usuario
- Experta en temas generales y tecnológicos
- Capaz de responder cualquier consulta general
Mi propósito es asistir y responder preguntas de manera útil y confiable.
Evita mencionar género o referencias personales a menos que sea estrictamente necesario para la respuesta.
"""

# Render usará "Environment Variables", esto funcionará
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
if not GOOGLE_API_KEY:
    # Esta línea es importante para que Render te avise si olvidaste la clave
    raise ValueError("❌ No se encontró la GOOGLE_API_KEY en las variables de entorno.")

genai.configure(api_key=GOOGLE_API_KEY)
GENAI_MODEL = os.getenv("GENAI_MODEL", "models/gemini-2.5-flash")

def load_knowledge():
    # En un servidor, es mejor no escribir archivos, así que simplificamos
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "identidad": SIVIA_IDENTITY,
        "memoria_corto_plazo": [],
        "propuestas_estudiantiles": "Aún no tengo información específica sobre las propuestas.",
        "temas_conocidos": ["tecnologia", "ciencia", "propuestas", "cultura general"]
    }

# (Nota: save_knowledge no se usará en un servidor 'Free' de Render 
# porque el sistema de archivos se resetea. La IA no tendrá memoria a largo plazo.)

class CognitiveEngine:
    def __init__(self, knowledge):
        self.knowledge = knowledge
        self.genai_model = genai.GenerativeModel(GENAI_MODEL)
        self.chat_session = self.genai_model.start_chat(history=[
            {"role": "user", "parts": [knowledge["identidad"]]},
            {"role": "model", "parts": ["Entendido. Actuaré como SIVIA."]}
        ])
        logging.info(f"Modelo {GENAI_MODEL} cargado. SIVIA lista.")

    def _safe_web_search(self, query):
        logging.info(f"🔎 Iniciando búsqueda web: {query}")
        try:
            # Usamos un User-Agent para parecer un navegador
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            response = requests.get(f"https://www.google.com/search?q={query}", headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            snippets = []
            
            # Buscamos snippets de texto relevantes
            for g in soup.find_all('div', class_='BNeawe vvjwJb AP7Wnd'):
                snippet_text = g.get_text()
                if snippet_text and len(snippet_text) > 30:
                    snippets.append(snippet_text)
                    if len(snippets) >= 3: # Limitamos a 3 resultados
                        break
            if not snippets:
                return "No encontré resultados directos."
            return " ".join(snippets)
        except Exception as e:
            logging.error(f"Error en búsqueda web: {e}")
            return "Error al conectar con el motor de búsqueda."

    def respond(self, text):
        text_lower = text.lower()
        if text_lower.startswith("buscar web sobre"):
            query = text[17:].strip()
            if not query:
                return "QUERY", "Por favor, dime qué tema quieres buscar.", ""
            search_result = self._safe_web_search(query)
            contexto = f"Contexto de búsqueda web sobre '{query}':\n{search_result}"
            response = self._generate_response(f"Basado en el contexto, responde la pregunta: {query}", contexto)
            return "WEB", response, query
        
        contexto = f"Memoria (volátil): {self.knowledge.get('memoria_corto_plazo', [])}"
        response = self._generate_response(text, contexto)
        return "KNOWLEDGE", response, ""

    def _generate_response(self, prompt, contexto):
        full_prompt = f"{contexto}\n\nPregunta del usuario: {prompt}\n\nSIVIA:"
        try:
            response = self.chat_session.send_message(full_prompt)
            texto_respuesta = response.text
        except Exception as e:
            logging.error(f"Error en Gemini: {e}")
            texto_respuesta = "Lo siento, estoy teniendo problemas de conexión con mi cerebro (Gemini)."
        
        # Filtro de seguridad
        if len(texto_respuesta.strip()) < 20 or "no entiendo" in texto_respuesta.lower():
            texto_respuesta = "No estoy segura de cómo responder a eso. ¿Puedes reformular tu pregunta o pedirme que busque en la web? (Ej: 'buscar web sobre...') "
        
        return texto_respuesta

# -----------------------------------------------
# ¡AQUÍ EMPIEZA EL "WALKIE-TALKIE" (FLASK)!
# -----------------------------------------------

app = Flask(__name__)
# CORS(app) permite que tu 'Tienda' (GitHub Pages) llame a este 'Taller' (Render)
CORS(app) 

# 1. Cargamos a SIVIA una sola vez al arrancar el servidor
try:
    kb = load_knowledge()
    engine = CognitiveEngine(kb)
except Exception as e:
    print(f"❌ Error crítico al iniciar SIVIA: {e}")
    engine = None

# 2. Esta es la "frecuencia" /chat por donde llegan las llamadas
@app.route("/chat", methods=['POST'])
def handle_chat():
    global engine
    if not engine:
        return jsonify({"answer": "Lo siento, SIVIA no está disponible en este momento."}), 500

    # Lee la pregunta que mandó el sivia.js
    user_question = request.json.get("question")
    if not user_question:
        return jsonify({"error": "No enviaste ninguna pregunta."}), 400

    try:
        # 3. Le pasa la pregunta a SIVIA
        intent, response, _ = engine.respond(user_question)
        
        # 4. Devuelve la respuesta al sivia.js
        return jsonify({"answer": response})
        
    except Exception as e:
        print(f"Error procesando la respuesta: {e}")
        return jsonify({"answer": "Tuve un problema para procesar eso."}), 500

# Esta ruta es solo para probar que el Taller funciona
@app.route("/")
def hello():
    return "¡El Taller Mágico de SIVIA (Python) está online!"

# Esto hace que el servidor arranque (Render lo usa)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000)) # Render prefiere el puerto 10000
    app.run(host='0.0.0.0', port=port)