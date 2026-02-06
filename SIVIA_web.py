import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR: Falta la API KEY")

# Configuramos la librería CLÁSICA
genai.configure(api_key=GOOGLE_API_KEY)

# 2. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 3. CONFIGURACIÓN DEL MODELO
# Usamos el nombre estándar que SIEMPRE funciona en esta librería
MODEL_NAME = "gemini-1.5-flash"

SYSTEM_INSTRUCTION = f"""
Eres SIVIA.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, USA GOOGLE SEARCH.
"""

# Definición de herramientas (Sintaxis para versión 0.8.3+)
tools_config = [
    {"google_search": {}}
]

# Iniciamos el modelo
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=SYSTEM_INSTRUCTION,
    tools=tools_config
)

@app.route('/', methods=['GET'])
def home():
    return "SIVIA CLÁSICA - ONLINE"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        if img_data:
            # === CASO IMAGEN ===
            # Nota: Gemini 1.5 Flash a veces no permite Search + Imagen simultáneo en tier gratis
            # Así que para imágenes, desactivamos tools temporalmente o usamos un modelo sin tools
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            # Usamos el modelo generativo directo para la imagen
            response = model.generate_content([user_msg, img])
            return jsonify({"answer": response.text})
            
        else:
            # === CASO TEXTO + BÚSQUEDA ===
            # Aquí sí usa las tools definidas arriba
            response = model.generate_content(user_msg)
            
            # Extraer respuesta con seguridad
            if response.text:
                return jsonify({"answer": response.text})
            elif response.candidates and response.candidates[0].content.parts:
                return jsonify({"answer": response.candidates[0].content.parts[0].text})
            else:
                return jsonify({"answer": "Busqué información pero no pude armar una respuesta."})

    except Exception as e:
        print(f"❌ ERROR: {e}")
        # Si el error es por seguridad o bloqueo, lo informamos
        return jsonify({"answer": f"Ocurrió un error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
