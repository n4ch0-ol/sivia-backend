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

# Configuración básica
genai.configure(api_key=GOOGLE_API_KEY)

# 2. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 3. INSTRUCCIONES
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, intenta responder con tu conocimiento general.
"""

# 4. INICIALIZACIÓN DEL MODELO (A PRUEBA DE FALLOS)
MODEL_NAME = "gemini-1.5-flash"
model = None

# Intento 1: Con Google Search activado
try:
    print("🔄 Intentando cargar modelo CON Google Search...")
    # Sintaxis diccionario compatible con 0.8.3
    tools_config = [{'google_search': {}}]
    
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
        tools=tools_config
    )
    # Hacemos una prueba tonta para ver si explota
    model._tools.to_proto() 
    print("✅ Google Search activado correctamente.")

except Exception as e:
    print(f"⚠️ FALLÓ LA CARGA DE SEARCH ({e}).")
    print("🔄 Cambiando a modo SOLO TEXTO/JSON para no detener el servidor.")
    
    # Intento 2: Sin herramientas (Esto NO puede fallar)
    try:
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION
        )
        print("✅ SIVIA iniciada en modo BÁSICO (Solo JSON + Chat).")
    except Exception as e2:
        print(f"❌ ERROR CRÍTICO FINAL: {e2}")

@app.route('/', methods=['GET'])
def home():
    status = "CON BÚSQUEDA" if model and hasattr(model, '_tools') and model._tools else "SOLO JSON"
    return f"SIVIA ONLINE - {status}"

@app.route('/chat', methods=['POST'])
def chat():
    if not model:
        return jsonify({"answer": "Error crítico: El modelo no pudo iniciarse."}), 500

    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        if img_data:
            # === CASO IMAGEN ===
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            # Para imágenes usamos el método directo sin tools para evitar conflictos
            response = model.generate_content([user_msg, img])
            return jsonify({"answer": response.text})
            
        else:
            # === CASO TEXTO ===
            response = model.generate_content(user_msg)
            
            if response.text:
                return jsonify({"answer": response.text})
            elif response.candidates and response.candidates[0].content.parts:
                return jsonify({"answer": response.candidates[0].content.parts[0].text})
            else:
                return jsonify({"answer": "No pude generar una respuesta."})

    except Exception as e:
        print(f"❌ ERROR EN CHAT: {e}")
        # Mensaje genérico para no asustar al usuario
        return jsonify({"answer": "Tuve un pequeño error interno, ¿puedes reformular la pregunta?"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
