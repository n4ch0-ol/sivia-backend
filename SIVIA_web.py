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
import time
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

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

# Nuevos archivos para persistencia ligera
USERS_FILE = "users.json"
VOTES_FILE = "votes.json"
JWT_SECRET = os.getenv("JWT_SECRET", "cambia_esto_por_una_clave_segura")

def load_json_or_default(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error leyendo {path}: {e}")
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error guardando {path}: {e}")

# Usuarios
def load_users():
    return load_json_or_default(USERS_FILE, {})

def save_users(users):
    save_json(USERS_FILE, users)

# Votos
def load_votes():
    return load_json_or_default(VOTES_FILE, {})

def save_votes(votes):
    save_json(VOTES_FILE, votes)

# Util: crear token JWT
def create_token(username, email):
    payload = {"sub": username, "email": email, "iat": int(time.time())}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token

def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        return None

# Decorator simple para endpoints protegidos
from functools import wraps
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "No autorizado"}), 401
        token = auth.split(" ", 1)[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Token inválido"}), 401
        request.user = payload  # attach
        return f(*args, **kwargs)
    return wrapper

# BÚSQUEDA LOCAL en knowledge (fallback)
def local_search_in_knowledge(knowledge, question):
    q = question.lower()
    # FAQs exact/contains
    for faq in knowledge.get("preguntas_frecuentes", []):
        if faq.get("pregunta") and faq["pregunta"].lower() in q:
            return faq.get("respuesta")
    # buscar por palabras clave en proyectos
    for p in knowledge.get("proyectos", []):
        if p.get("nombre") and p["nombre"].lower() in q:
            return p.get("descripcion")
    # fallback: return short summary
    return "No tengo una respuesta exacta en la base local. Puedo intentar buscar en la web si quieres."

# Mejorar _generate_response con retries/backoff y fallback
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
        """Genera respuesta usando Gemini con retries y fallback local."""
        full_message = f"{prompt}\n{contexto}" if contexto else prompt
        max_retries = 3
        backoff = 1
        for attempt in range(1, max_retries + 1):
            try:
                response = self.chat_session.send_message(full_message)
                texto_respuesta = response.text
                # si respuesta vacía o corta, continuar/intent
                if texto_respuesta and len(texto_respuesta.strip()) >= 10:
                    return texto_respuesta
            except Exception as e:
                err = str(e).lower()
                logging.error(f"Error en Gemini intento {attempt}: {e}")
                # detectar límites
                if "quota" in err or "rate" in err or "limit" in err or "exceeded" in err:
                    logging.warning("Detected quota/rate error from Gemini, will fallback to local knowledge.")
                    # fallback local usando la knowledge cargada
                    return local_search_in_knowledge(self.knowledge, prompt)
                # en otros errores: reintentar con backoff
            time.sleep(backoff)
            backoff *= 2
        # Si agotó reintentos, fallback local
        return local_search_in_knowledge(self.knowledge, prompt)

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

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.json or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not username or not email or not password:
        return jsonify({"error": "username, email y password son requeridos"}), 400
    # dominio permitido
    if not email.endswith("@colegioaprenderes.edu.ar"):
        return jsonify({"error": "Solo cuentas del colegio están permitidas"}), 403
    users = load_users()
    if email in users:
        return jsonify({"error": "Usuario ya registrado"}), 400
    users[email] = {
        "username": username,
        "password_hash": generate_password_hash(password),
        "created_at": datetime.utcnow().isoformat()
    }
    save_users(users)
    token = create_token(username, email)
    return jsonify({"message": "Registrado", "token": token, "username": username})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "email y password son requeridos"}), 400
    users = load_users()
    user = users.get(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Credenciales inválidas"}), 401
    token = create_token(user["username"], email)
    return jsonify({"message": "Autenticado", "token": token, "username": user["username"]})

@app.route("/api/vote", methods=["POST"])
@require_auth
def api_vote():
    data = request.json or {}
    experiment = data.get("experiment")
    vote = int(data.get("vote", 0))
    if not experiment or vote not in (1, -1):
        return jsonify({"error": "Parametros invalidos"}), 400
    votes = load_votes()
    if experiment not in votes:
        votes[experiment] = {"util": 0, "noUtil": 0}
    if vote > 0:
        votes[experiment]["util"] += 1
    else:
        votes[experiment]["noUtil"] += 1
    save_votes(votes)
    return jsonify({"message": "Voto registrado", "votes": votes[experiment]})

# Nuevo: obtener perfil del token
@app.route("/api/profile", methods=["GET"])
@require_auth
def api_profile():
    payload = request.user  # inyectado por require_auth
    return jsonify({
        "username": payload.get("sub"),
        "email": payload.get("email")
    })

# Nuevo: devolver todos los votos
@app.route("/api/votes", methods=["GET"])
def api_votes():
    votes = load_votes()
    return jsonify(votes)

# Nuevo: devolver votos de un experimento concreto
@app.route("/api/votes/<experiment>", methods=["GET"])
def api_votes_experiment(experiment):
    votes = load_votes()
    exp = votes.get(experiment)
    if not exp:
        return jsonify({"util": 0, "noUtil": 0})
    return jsonify(exp)
