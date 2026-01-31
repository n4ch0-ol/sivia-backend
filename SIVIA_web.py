import os
import json
import logging
import base64
import google.generativeai as genai
from google.generativeai.types import content_types
from google.api_core import exceptions
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

KNOWLEDGE_FILE = "knowledge_sivia.json"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    # Fallback para pruebas locales si no hay variable
    logging.warning("⚠️ No hay API KEY. SIVIA no funcionará correctamente.")

# Configuración global de la API
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- DEFINICIÓN DE LA INTELIGENCIA (SYSTEM PROMPT) ---
# Aquí es donde le prohibimos Wikipedia y le obligamos a usar fuentes serias
SYSTEM_INSTRUCTION = """
Eres SIVIA (Sistema de Innovación Virtual con Inteligencia Aplicada).
TU IDENTIDAD:
- Eres profesional, empática y altamente eficiente.
- Eres la asistente oficial del centro de estudiantes/organización.

REGLAS DE BÚSQUEDA E INFORMACIÓN:
1. Cuando necesites buscar información, PRIORIZA SITIOS con terminación .edu, .gov, .org y papers académicos.
2. 🚫 ESTÁ PROHIBIDO USAR WIKIPEDIA como fuente primaria. Si la información viene de ahí, verifícala con otra fuente.
3. Si te piden noticias, busca fuentes periodísticas reconocidas.

CAPACIDADES:
- Puedes ver y analizar imágenes que te envíen.
- Puedes generar imágenes (usando la herramienta externa).
- Puedes simular la creación de conceptos de video.
"""

def load_knowledge():
    """Carga la base de conocimientos local."""
    data = {"identidad": SYSTEM_INSTRUCTION} # Fallback por defecto
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                # Combinamos la instrucción del sistema con los datos del JSON
                if "identidad" in file_data:
                    data["identidad"] += "\n\nDatos específicos: " + file_data["identidad"]
                return data
        except Exception as e:
            logging.error(f"Error leyendo JSON: {e}")
    return data

class CognitiveEngine:
    def __init__(self, knowledge):
        self.knowledge = knowledge
        self.model_name = "gemini-1.5-flash"
        
        # --- INTENTO DE ACTIVACIÓN DE DEEP RESEARCH ---
        try:
            # Intentamos cargar el modelo con herramientas de búsqueda
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.knowledge["identidad"],
                tools=[{"google_search_retrieval": {
                    "dynamic_retrieval_config": {
                        "mode": "dynamic",
                        "dynamic_threshold": 0.6
                    }
                }}]
            )
            # Prueba de fuego: Iniciamos chat vacío para ver si la API responde o da 404
            self.chat = self.model.start_chat(history=[])
            logging.info("✅ SIVIA: Modo AVANZADO activado (Búsqueda Web + Visión).")
            self.mode = "advanced"
            
        except Exception as e:
            logging.warning(f"⚠️ Modo Avanzado falló ({e}). Activando modo ESTÁNDAR.")
            # FALLBACK: Si falla la búsqueda (error 404/v1beta), cargamos el modelo pelado
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.knowledge["identidad"]
            )
            self.chat = self.model.start_chat(history=[])
            self.mode = "standard"

    def respond(self, text, image_b64=None):
        content_parts = []
        text_lower = text.lower() if text else ""

        # --- 1. DETECCIÓN DE COMANDOS DE GENERACIÓN (IMAGEN/VIDEO) ---
        if "genera" in text_lower or "dibuja" in text_lower or "crea un video" in text_lower:
            prompt = text_lower.replace("genera", "").replace("dibuja", "").replace("una imagen de", "").replace("un video de", "").strip()
            
            # Truco para "Video": Generamos una imagen cinemática wide
            if "video" in text_lower:
                url = f"https://image.pollinations.ai/prompt/cinematic%20movie%20scene%20{prompt.replace(' ', '%20')}?width=1920&height=1080&nologo=true&model=flux"
                return f"🎥 He generado este concepto visual para tu video: {url}"
            else:
                # Imagen normal
                url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
                return f"🎨 Aquí tienes la imagen solicitada: {url}"

        # --- 2. MULTIMODALIDAD (VISIÓN) ---
        if image_b64:
            try:
                # Gemini requiere la imagen como blob
                content_parts.append({
                    "mime_type": "image/jpeg",
                    "data": image_b64
                })
                logging.info("📸 Procesando imagen entrante...")
            except Exception as e:
                logging.error(f"Error procesando imagen: {e}")

        # --- 3. TEXTO Y CONTEXTO ---
        # Si estamos en modo búsqueda, añadimos instrucciones de filtrado extra al prompt
        search_instruction = ""
        if self.mode == "advanced":
            search_instruction = "(Recuerda: Si buscas en web, usa solo dominios .edu, .gov, .org. NO Wikipedia)."
        
        full_message = f"{search_instruction}\nUsuario: {text}"
        content_parts.append(full_message)

        # --- 4. ENVÍO AL MODELO ---
        try:
            # Usamos send_message para mantener el hilo de la conversación
            response = self.chat.send_message(content_parts)
            return response.text
        except exceptions.NotFound:
            # Si se rompe la sesión por error 404 en medio del chat
            return "⚠️ Error de conexión con Google. Por favor, reinicia el chat."
        except Exception as e:
            logging.error(f"Error en respuesta: {e}")
            # Intento de recuperación sin historial
            try:
                response = self.model.generate_content(content_parts)
                return response.text
            except:
                return "Lo siento, mis sistemas neuronales están saturados. Intenta de nuevo."

# --- SERVIDOR FLASK ---
app = Flask(__name__)
CORS(app)

# Inicialización
try:
    kb = load_knowledge()
    engine = CognitiveEngine(kb)
except Exception as e:
    logging.critical(f"❌ Error Fatal: {e}")
    engine = None

@app.route("/chat", methods=['POST'])
def handle_chat():
    if not engine:
        return jsonify({"answer": "SIVIA se está reiniciando..."}), 503
    
    data = request.json
    pregunta = data.get("question", "")
    imagen = data.get("image") # Base64

    respuesta = engine.respond(pregunta, imagen)
    return jsonify({"answer": respuesta})

@app.route("/")
def index():
    estado = "Avanzado (Búsqueda Activa)" if engine and engine.mode == "advanced" else "Estándar (Estable)"
    return f"SIVIA Backend Online. Estado: {estado}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
