import os
import json
import base64
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image

# --- IMPORTAMOS LA NUEVA LIBRERÍA (SDK v2) ---
from google import genai
from google.genai import types

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

# 2. CONFIGURACIÓN DEL CLIENTE
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR FATAL: No se encontró la GOOGLE_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)

# ==============================================================================
#  CONFIGURACIÓN DEL MODELO - SOLUCIÓN DEFINITIVA
# ==============================================================================
# NO usamos autodetección.
# Usamos el ID EXACTO de la versión estable 001.
# Esto evita que la librería se confunda con los alias.
MODEL_NAME = "gemini-1.5-flash-001" 

print(f"🚀 SIVIA INICIADA. Usando ID específico: {MODEL_NAME}")

# 3. BASE DE DATOS (JSON)
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos disponibles."

# 4. INSTRUCCIONES
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, USA GOOGLE SEARCH.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")
        
        # Herramienta de búsqueda activada
        tools_config = [types.Tool(google_search=types.GoogleSearch())]
        
        response_text = ""

        if img_data:
            # === CASO IMAGEN ===
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            # Enrutamos la llamada al modelo
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[user_msg, img],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.4
                )
            )
            response_text = response.text
            
        else:
            # === CASO TEXTO (CON BÚSQUEDA) ===
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tools_config,
                    temperature=0.4,
                    response_modalities=["TEXT"] # Forzamos respuesta texto
                )
            )
            
            # Lógica de extracción de respuesta
            if response.text:
                response_text = response.text
            elif response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                if part.text:
                    response_text = part.text
                else:
                    response_text = "He encontrado información pero no puedo mostrarla en este formato."
            else:
                response_text = "Lo siento, hubo un problema generando la respuesta."

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN CHAT: {e}")
        # Mensaje de error limpio para el frontend
        return jsonify({"answer": "Estoy teniendo problemas de conexión con Google. Intenta de nuevo en unos segundos."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
