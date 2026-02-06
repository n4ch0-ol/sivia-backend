import os
import json
import base64
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image

# Importamos la librería clásica y sus "Protos" (los objetos crudos)
import google.generativeai as genai
from google.generativeai import protos

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR: Falta la API KEY")

# Configuramos la librería
genai.configure(api_key=GOOGLE_API_KEY)

# 2. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 3. CONFIGURACIÓN DEL MODELO (A PRUEBA DE BOMBAS)
MODEL_NAME = "gemini-1.5-flash"

SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, USA GOOGLE SEARCH.
"""

# --- AQUÍ ESTÁ EL ARREGLO ---
# En lugar de usar un diccionario que confunde al sistema, creamos el objeto Tool manualmente.
# Esto obliga a la librería a aceptar la herramienta de búsqueda sin rechistar.
try:
    sivia_tools = [
        protos.Tool(google_search=protos.GoogleSearch())
    ]
    print("✅ Herramienta Google Search configurada manualmente.")
except Exception as e:
    print(f"⚠️ Alerta: No se pudo cargar Google Search ({e}). Iniciando sin búsqueda.")
    sivia_tools = None

# Iniciamos el modelo
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=SYSTEM_INSTRUCTION,
    tools=sivia_tools
)

@app.route('/', methods=['GET'])
def home():
    return "SIVIA (Classic Hardcoded) - ONLINE"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        if img_data:
            # === CASO IMAGEN ===
            # Las imágenes a veces chocan con las tools en la versión gratuita.
            # Generamos contenido directamente sin tools para asegurar que funcione.
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            response = model.generate_content([user_msg, img])
            return jsonify({"answer": response.text})
            
        else:
            # === CASO TEXTO ===
            # Aquí usa las herramientas configuradas (Search)
            response = model.generate_content(user_msg)
            
            # Extracción de respuesta a prueba de fallos
            if response.text:
                return jsonify({"answer": response.text})
            elif response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                return jsonify({"answer": part.text if part.text else "Encontré información pero no pude procesar el texto."})
            else:
                return jsonify({"answer": "Lo siento, no pude generar una respuesta."})

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"answer": "Error momentáneo en el servidor de IA."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
