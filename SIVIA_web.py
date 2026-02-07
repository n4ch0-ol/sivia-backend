import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64
import sys

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR: Falta API KEY", file=sys.stderr)

genai.configure(api_key=GOOGLE_API_KEY)

# 2. SELECCIÓN DE MODELO (SUPERVIVENCIA)
# Lista de candidatos ordenada por preferencia (velocidad/coste)
CANDIDATE_MODELS = [
    "gemini-1.5-flash-001", # Versión específica (suele arreglar el 404)
    "gemini-1.5-flash",     # Alias genérico
    "gemini-1.5-flash-8b",  # Versión ligera
    "gemini-1.5-pro",       # Versión Pro
    "gemini-1.0-pro",       # El viejo confiable
    "gemini-pro"            # Alias legacy
]

active_model = None
selected_model_name = "Ninguno"

def initialize_model():
    global active_model, selected_model_name
    
    # Datos del sistema
    try:
        with open('knowledge_base.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            db_content = json.dumps(data, indent=2, ensure_ascii=False)
    except:
        db_content = "No hay datos."

    system_instruction = f"Eres SIVIA. Datos: {db_content}. Responde brevemente."

    print("🔄 Iniciando prueba de modelos...", file=sys.stdout)
    
    for model_name in CANDIDATE_MODELS:
        try:
            print(f"🧪 Probando: {model_name}...", file=sys.stdout)
            test_model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction
            )
            # Hacemos una prueba REAL de generación (un "Hola")
            # Si esto falla (404 o 429), saltará al except
            response = test_model.generate_content("Hola, test de conexión.")
            
            if response and response.text:
                active_model = test_model
                selected_model_name = model_name
                print(f"✅ ¡ÉXITO! Conectado a: {model_name}", file=sys.stdout)
                return # Salimos del bucle, ya tenemos ganador
                
        except Exception as e:
            print(f"⚠️ Falló {model_name}: {e}", file=sys.stderr)
            continue # Probamos el siguiente
            
    print("❌ TODOS LOS MODELOS FALLARON. Revisa tu API Key o Plan.", file=sys.stderr)

# Ejecutamos la selección al arrancar
initialize_model()

@app.route('/', methods=['GET'])
def home():
    status = "ONLINE" if active_model else "OFFLINE (Error Modelos)"
    return f"SIVIA {status} - Usando: {selected_model_name}"

@app.route('/chat', methods=['POST'])
def chat():
    # Si no hay modelo, intentamos reconectar una vez más
    if not active_model:
        initialize_model()
        if not active_model:
            return jsonify({"answer": "Error crítico: Ningún modelo de Google funciona en tu cuenta."}), 500

    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        if img_data:
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            response = active_model.generate_content([user_msg, img])
            return jsonify({"answer": response.text})
        else:
            response = active_model.generate_content(user_msg)
            return jsonify({"answer": response.text})

    except Exception as e:
        print(f"❌ Error chat: {e}", file=sys.stderr)
        return jsonify({"answer": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
