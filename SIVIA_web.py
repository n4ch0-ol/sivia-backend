import os
import json
import logging
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# Usamos v1beta obligatoriamente para tener acceso a 'tools' (Búsqueda)
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"

# --- GESTOR DE CONOCIMIENTO ---
def load_knowledge():
    """Carga knowledge_base.json y construye la personalidad."""
    filename = "knowledge_base.json"
    
    # Identidad base por si falla el archivo
    base_identity = """
    Eres SIVIA, una IA avanzada y profesional.
    1. Tienes acceso a Búsqueda de Google: Úsala para dar datos actualizados (noticias, clima, hechos recientes).
    2. Tus respuestas deben ser COMPLETAS, detalladas y bien estructuradas. No seas breve.
    3. Si te preguntan sobre tí o la organización, usa la información de tu base de datos.
    4. Ignora Wikipedia. Prioriza fuentes .edu, .org, .gob.
    """
    
    contexto_json = ""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convertimos todo el JSON a texto para que la IA lo lea
                contexto_json = json.dumps(data, ensure_ascii=False, indent=2)
                logging.info(f"✅ BASE DE DATOS CARGADA: {filename}")
        except Exception as e:
            logging.error(f"❌ Error leyendo JSON: {e}")
    else:
        logging.warning(f"⚠️ No encontré el archivo: {filename}")

    # Combinamos todo en un super-prompt
    return f"{base_identity}\n\nINFORMACIÓN DE BASE DE DATOS INTERNA:\n{contexto_json}"

# --- MOTOR COGNITIVO (HTTP RAW CON SEARCH) ---
def call_gemini_with_search(user_text, image_b64=None):
    if not GOOGLE_API_KEY: return "Error: Falta API Key."

    headers = {"Content-Type": "application/json"}
    
    # 1. Construimos el contenido multimedia o texto
    parts = []
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
    
    parts.append({"text": user_text})

    # 2. El Payload Mágico (Aquí activamos Google Search a mano)
    payload = {
        "contents": [{
            "parts": parts
        }],
        # INSTRUCCIÓN DE SISTEMA (Identidad + JSON)
        "system_instruction": {
            "parts": [{"text": load_knowledge()}]
        },
        # HERRAMIENTAS (Esto activa la búsqueda web real)
        "tools": [
            {"googleSearchRetrieval": {
                "dynamicRetrievalConfig": {
                    "mode": "dynamic",
                    "dynamicThreshold": 0.6
                }
            }}
        ]
    }

    try:
        # Hacemos la petición POST directa
        response = requests.post(API_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Navegamos la respuesta compleja de Google
            try:
                candidate = data['candidates'][0]
                content_parts = candidate['content']['parts']
                
                # A veces la respuesta viene troceada, unimos las partes de texto
                full_response = ""
                for part in content_parts:
                    if 'text' in part:
                        full_response += part['text']
                
                return full_response if full_response else "No pude generar texto (quizás solo busqué)."
            except Exception as e:
                return f"Error procesando respuesta de Google: {str(e)} - Data: {str(data)[:100]}"
        else:
            return f"⚠️ Error Google ({response.status_code}): {response.text}"
            
    except Exception as e:
        return f"Error de conexión fatal: {str(e)}"

# --- SERVIDOR FLASK ---
app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=['POST'])
def handle_chat():
    data = request.json
    if not data: return jsonify({"answer": "Error de datos"}), 400
    
    q = data.get("question", "")
    img = data.get("image")
    
    # --- DETECTOR DE GENERACIÓN DE IMAGEN/VIDEO ---
    text_lower = q.lower()
    keywords_img = ["genera una imagen", "dibuja", "crea una foto", "ilustra"]
    keywords_vid = ["genera un video", "crea un video", "haz un video"]

    # 1. Lógica de Video (Simulado con Flux Cinematic)
    if any(k in text_lower for k in keywords_vid):
        prompt = text_lower
        for k in keywords_vid: prompt = prompt.replace(k, "")
        prompt = prompt.replace("de", "", 1).strip()
        
        url = f"https://image.pollinations.ai/prompt/cinematic%20movie%20scene%20HQ%204k%20{prompt.replace(' ','%20')}?width=1920&height=1080&nologo=true&model=flux"
        return jsonify({"answer": f"🎬 He generado el concepto para tu video: {url}"})

    # 2. Lógica de Imagen (Simulada)
    if any(k in text_lower for k in keywords_img):
        prompt = text_lower
        for k in keywords_img: prompt = prompt.replace(k, "")
        prompt = prompt.replace("de", "", 1).strip()
        
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ','%20')}?width=1024&height=1024&nologo=true"
        return jsonify({"answer": f"🎨 Aquí tienes la imagen: {url}"})

    # 3. Consulta Inteligente (Texto + Búsqueda + JSON)
    respuesta = call_gemini_with_search(q, img)
    return jsonify({"answer": respuesta})

@app.route("/")
def home(): 
    return "SIVIA Ultimate Online"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
