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

# Instanciamos el cliente
client = genai.Client(api_key=GOOGLE_API_KEY)

# ==============================================================================
#  FUNCIÓN DE AUTO-SELECCIÓN DE MODELO (CORREGIDA Y BLINDADA)
# ==============================================================================
def select_optimal_model():
    print("--- 🔍 ANALIZANDO MODELOS DISPONIBLES... ---")
    selected_model = "gemini-1.5-flash" # Valor por defecto SEGURO (sin models/)

    try:
        # Obtenemos todos los modelos
        all_models = list(client.models.list())
        
        for m in all_models:
            # El nombre crudo suele ser 'models/gemini-1.5-flash-001'
            raw_name = m.name
            name_lower = raw_name.lower()
            
            # TU LÓGICA DE FILTRADO (1.5 + gemini + flash)
            if "gemini" in name_lower and "1.5" in name_lower and "flash" in name_lower:
                selected_model = raw_name
                print(f"✨ Encontrado candidato: {selected_model}")
                break # Nos quedamos con el primero que coincida
        
    except Exception as e:
        print(f"⚠️ Error listando modelos ({e}). Usando default: {selected_model}")

    # === LIMPIEZA BRUTAL DEL NOMBRE (CRUCIAL) ===
    # La nueva API odia el prefijo "models/". Lo cortamos sí o sí.
    if selected_model.startswith("models/"):
        clean_name = selected_model.split("/")[-1] # Toma solo lo que está después de la barra
        print(f"✂️  Nombre corregido: '{selected_model}' -> '{clean_name}'")
        return clean_name
    
    return selected_model

# EJECUTAMOS LA SELECCIÓN
MODEL_NAME = select_optimal_model()
print(f"🚀 SIVIA USARÁ EL MODELO FINAL: '{MODEL_NAME}'")


# 3. BASE DE DATOS (JSON)
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos disponibles."

# 4. INSTRUCCIONES DEL SISTEMA
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, USA GOOGLE SEARCH.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - Model: {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")
        
        # Herramienta de búsqueda
        tools_config = [types.Tool(google_search=types.GoogleSearch())]
        
        response_text = ""

        if img_data:
            # === CASO IMAGEN ===
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
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
                    response_modalities=["TEXT"]
                )
            )
            
            if response.text:
                response_text = response.text
            elif response.candidates and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text
            else:
                response_text = "No pude generar respuesta."

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"❌ ERROR EN CHAT: {e}")
        return jsonify({"answer": f"Error del sistema: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
