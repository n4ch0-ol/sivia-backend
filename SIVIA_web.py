import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64

# 1. CARGA DE VARIABLES Y CONFIGURACIÓN
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# 2. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 3. CONFIGURACIÓN DEL MODELO (FORZADO A 1.5 FLASH)
# Usamos este modelo porque es 100% compatible con la búsqueda actual
MODEL_NAME = "models/gemini-1.5-flash"

# Herramienta de búsqueda (Sintaxis estándar)
tools_sivia = [
    {"google_search": {}}
]

SYSTEM_INSTRUCTION = f"""
Eres SIVIA.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, USA GOOGLE SEARCH.
"""

# Iniciamos el modelo
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=SYSTEM_INSTRUCTION,
    tools=tools_sivia
)

@app.route('/', methods=['GET'])
def home():
    return "SIVIA ONLINE - SEARCH ENABLED"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        # Si hay imagen, Gemini a veces desactiva tools automáticamente, 
        # así que manejamos el error o procesamos sin tools
        if data.get("image"):
            # Lógica simple para imagen
            return jsonify({"answer": "Procesando imagen..."}) 
        else:
            # Lógica texto con búsqueda
            response = model.generate_content(data.get("question"))
            return jsonify({"answer": response.text})
    except Exception as e:
        return jsonify({"answer": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
