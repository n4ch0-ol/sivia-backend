import os
import json
import base64
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image

# --- IMPORTAMOS LA NUEVA LIBRERÍA ---
from google import genai
from google.genai import types

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

# 2. CONFIGURACIÓN DEL CLIENTE (NUEVA SINTAXIS)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR: No hay API KEY")

# Instanciamos el cliente nuevo
client = genai.Client(api_key=GOOGLE_API_KEY)

# 3. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 4. CONFIGURACIÓN DEL MODELO Y HERRAMIENTAS
# Usamos el modelo 2.0 Flash que es nativo de esta nueva librería y vuela.
MODEL_NAME = "gemini-1.5-flash"

SYSTEM_INSTRUCTION = f"""
Eres SIVIA.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, USA GOOGLE SEARCH.
"""

@app.route('/', methods=['GET'])
def home():
    return "SIVIA RELOADED (New GenAI SDK) - ONLINE"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")
        
        # Configuración de herramientas para esta llamada
        # Activamos Google Search explícitamente
        tools_config = [types.Tool(google_search=types.GoogleSearch())]
        
        response_text = ""

        if img_data:
            # CASO IMAGEN
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            # En la nueva librería, pasamos la imagen directamente
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[user_msg, img],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.4
                    # Nota: A veces Search se desactiva con imágenes, es normal
                )
            )
            response_text = response.text
            
        else:
            # CASO TEXTO + BÚSQUEDA
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tools_config, # <--- Aquí activamos la búsqueda
                    temperature=0.4,
                    response_modalities=["TEXT"]
                )
            )
            
            # Verificamos si hay texto en la respuesta
            if response.text:
                response_text = response.text
            else:
                # A veces la respuesta viene en 'candidates' si usa herramientas complejas
                response_text = "He encontrado información pero necesito procesarla mejor."
                if response.candidates and response.candidates[0].content.parts:
                     response_text = response.candidates[0].content.parts[0].text

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"answer": f"Error del sistema: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

