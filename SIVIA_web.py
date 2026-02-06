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
#  FUNCIÓN DE AUTO-SELECCIÓN DE MODELO (TU PEDIDO)
# ==============================================================================
def select_optimal_model():
    """
    Busca en la lista de modelos disponibles uno que cumpla:
    1. Contenga 'gemini'
    2. Contenga '1.5' (para evitar el 2.0 que da error de cuota)
    3. Contenga 'flash' (para velocidad)
    """
    print("--- 🔍 ANALIZANDO MODELOS DISPONIBLES... ---")
    try:
        # Obtenemos todos los modelos de la cuenta
        all_models = list(client.models.list())
        
        for m in all_models:
            # El nombre suele venir como 'models/gemini-1.5-flash-001'
            name = m.name
            name_lower = name.lower()
            
            # TU LÓGICA DE FILTRADO:
            if "gemini" in name_lower and "1.5" in name_lower and "flash" in name_lower:
                
                # IMPORTANTE: La nueva librería requiere el nombre SIN "models/"
                # Ejemplo: transformar 'models/gemini-1.5-flash' -> 'gemini-1.5-flash'
                clean_name = name.replace("models/", "")
                
                print(f"✅ MODELO ELEGIDO: {clean_name} (Origen: {name})")
                return clean_name
        
        # Si termina el bucle y no encuentra nada, usamos fallback
        print("⚠️ No se encontró coincidencia exacta. Usando default.")
        return "gemini-1.5-flash"

    except Exception as e:
        print(f"❌ Error al listar modelos ({e}). Usando default seguro.")
        return "gemini-1.5-flash"

# EJECUTAMOS LA SELECCIÓN
MODEL_NAME = select_optimal_model()


# 3. BASE DE DATOS (JSON)
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
        print("📚 Base de datos cargada.")
except:
    database_content = "No hay datos específicos disponibles."
    print("⚠️ No se encontró knowledge_base.json")

# 4. INSTRUCCIONES DEL SISTEMA
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Si la respuesta no está en los datos locales, USA GOOGLE SEARCH.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - Running on: {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")
        
        # Configuramos la herramienta de búsqueda para esta petición
        # (Se activa si el modelo necesita información externa)
        tools_config = [types.Tool(google_search=types.GoogleSearch())]
        
        response_text = ""

        if img_data:
            # === CASO IMAGEN ===
            # Procesamos base64 a imagen PIL
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            # Enviamos al modelo (Normalmente search se deshabilita con imágenes en tiers bajos)
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
                    tools=tools_config, # <--- Aquí activamos Google Search
                    temperature=0.4,
                    response_modalities=["TEXT"]
                )
            )
            
            # Extracción segura de la respuesta
            if response.text:
                response_text = response.text
            elif response.candidates and response.candidates[0].content.parts:
                # A veces la respuesta viene estructurada si usó herramientas
                response_text = response.candidates[0].content.parts[0].text
            else:
                response_text = "Lo siento, intenté buscar eso pero no pude generar una respuesta coherente."

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"❌ ERROR EN CHAT: {e}")
        return jsonify({"answer": f"Hubo un error interno: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
