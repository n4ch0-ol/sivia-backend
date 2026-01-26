import os
import json
import logging
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

KNOWLEDGE_FILE = "knowledge_base.json"  # ← CAMBIO AQUÍ
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

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
if not GOOGLE_API_KEY:
    raise ValueError("❌ No se encontró la GOOGLE_API_KEY en las variables de entorno.")

genai.configure(api_key=GOOGLE_API_KEY)
GENAI_MODEL = os.getenv("GENAI_MODEL", "models/gemini-2.5-flash")

def load_knowledge():
    """Carga la base de conocimiento JSON"""
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                knowledge = json.load(f)
                logging.info("✅ Base de conocimiento cargada exitosamente")
                return knowledge
        except json.JSONDecodeError:
            logging.error("❌ Error al parsear el JSON")
            return get_default_knowledge()
    else:
        logging.warning(f"⚠️ {KNOWLEDGE_FILE} no encontrado, usando base vacía")
        return get_default_knowledge()

def get_default_knowledge():
    """Retorna una estructura por defecto si no hay JSON"""
    return {
        "metadata": {
            "version": "1.0",
            "organization": "Manos Unidas"
        },
        "proyectos": [],
        "formularios": [],
        "preguntas_frecuentes": [],
        "identidad": SIVIA_IDENTITY,
        "memoria_corto_plazo": []
    }

class CognitiveEngine:
    def __init__(self, knowledge):
        self.knowledge = knowledge
        self.genai_model = genai.GenerativeModel(GENAI_MODEL)
        
        # Crear un contexto con la base de datos
        context = self._build_context()
        
        self.chat_session = self.genai_model.start_chat(history=[
            {"role": "user", "parts": [context]},
            {"role": "model", "parts": ["Entendido. Soy SIVIA, asistente de Manos Unidas. Tengo toda la información del sitio disponible."]}
        ])
        logging.info(f"✅ Modelo {GENAI_MODEL} cargado. SIVIA lista con contexto completo.")

    def _build_context(self):
        """Construye el contexto a partir de la base de conocimiento"""
        projects_info = json.dumps(self.knowledge.get("proyectos", []), indent=2, ensure_ascii=False)
        faqs_info = json.dumps(self.knowledge.get("preguntas_frecuentes", []), indent=2, ensure_ascii=False)
        forms_info = json.dumps(self.knowledge.get("formularios", []), indent=2, ensure_ascii=False)
        
        context = f"""
{SIVIA_IDENTITY}

BASE DE CONOCIMIENTO DE MANOS UNIDAS:

PROYECTOS:
{projects_info}

PREGUNTAS FRECUENTES:
{faqs_info}

FORMULARIOS:
{forms_info}

Usa esta información para responder preguntas sobre Manos Unidas de manera precisa y amigable.
"""
        return context

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
        """Responde a la pregunta del usuario"""
        text_lower = text.lower()
        
        # Si pregunta por web, busca en internet
        if text_lower.startswith("buscar web sobre"):
            query = text[17:].strip()
            if not query:
                return "QUERY", "Por favor, dime qué tema quieres buscar.", ""
            search_result = self._safe_web_search(query)
            response = self._generate_response(f"Responde sobre: {query}", search_result)
            return "WEB", response, query
        
        # Si no, usa la base de conocimiento local
        response = self._generate_response(text, "")
        return "KNOWLEDGE", response, ""

    def _generate_response(self, prompt, contexto=""):
        """Genera respuesta usando Gemini"""
        try:
            full_message = f"{prompt}\n{contexto}" if contexto else prompt
            response = self.chat_session.send_message(full_message)
            texto_respuesta = response.text
        except Exception as e:
            logging.error(f"❌ Error en Gemini: {e}")
            texto_respuesta = "Lo siento, estoy teniendo problemas de conexión."
        
        if len(texto_respuesta.strip()) < 10:
            texto_respuesta = "No estoy segura de cómo responder eso. ¿Puedes reformular tu pregunta?"
        
        return texto_respuesta

# -----------------------------------------------
# FLASK - EL "WALKIE-TALKIE"
# -----------------------------------------------

app = Flask(__name__)
CORS(app)  # Permite que GitHub Pages llame a este servidor

# Cargar SIVIA al iniciar
try:
    kb = load_knowledge()
    engine = CognitiveEngine(kb)
    logging.info("🤖 SIVIA iniciada correctamente")
except Exception as e:
    logging.error(f"❌ Error crítico al iniciar SIVIA: {e}")
    engine = None

@app.route("/chat", methods=['POST'])
def handle_chat():
    """Endpoint que recibe preguntas del sitio web"""
    global engine
    
    if not engine:
        return jsonify({"answer": "SIVIA no está disponible en este momento."}), 500

    try:
        data = request.json
        user_question = data.get("question")
        
        if not user_question:
            return jsonify({"error": "No enviaste ninguna pregunta."}), 400

        # Procesar con SIVIA
        intent, response, _ = engine.respond(user_question)
        
        logging.info(f"✅ Pregunta: {user_question[:50]}... | Respuesta: {response[:50]}...")
        
        return jsonify({
            "answer": response,
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"❌ Error procesando: {e}")
        return jsonify({"answer": "Tuve un problema procesando tu pregunta."}), 500

@app.route("/")
def hello():
    """Test endpoint"""
    return "🤖 SIVIA Backend está online y listo"

@app.route("/health")
def health():
    """Health check para Render"""
    return jsonify({"status": "online", "sivia": "ready"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
