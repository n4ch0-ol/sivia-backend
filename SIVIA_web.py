import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurar API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("ERROR FATAL: No se encontró la GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)

# ==========================================
# 1. CARGAR TU BASE DE DATOS (knowledge_base.json)
# ==========================================
database_content = ""
try:
    # AQUÍ ESTÁ EL CAMBIO: Ahora busca 'knowledge_base.json'
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        # Convertimos el JSON a texto para que la IA lo entienda
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
        print("--- ✅ BASE DE DATOS (knowledge_base.json) CARGADA ---")
except Exception as e:
    print(f"--- ⚠️ ALERTA: No se pudo leer knowledge_base.json: {e} ---")
    database_content = "No hay datos específicos disponibles. Usa tu conocimiento general."

# ==========================================
# 2. AUTO-DETECTAR EL MEJOR MODELO
# ==========================================
def get_best_model():
    print("--- BUSCANDO MODELOS DISPONIBLES ---")
    valid_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
    except Exception as e:
        print(f"Error listando modelos: {e}")
        return "models/gemini-pro"

    preferences = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro"]
    for pref in preferences:
        if pref in valid_models:
            return pref
    
    if valid_models: return valid_models[0]
    return "models/gemini-pro"

MODEL_NAME = get_best_model()
print(f"--- SIVIA USARÁ EL MODELO: {MODEL_NAME} ---")

# ==========================================
# 3. INSTRUCCIONES DEL CEREBRO (SIVIA)
# ==========================================
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA oficial del Centro de Estudiantes "Manos Unidas".
Tu personalidad es útil, joven, empática y clara.

--- TU CONOCIMIENTO REAL (IMPORTANTE) ---
Toda la verdad sobre horarios, materias, precios y quiénes somos está en estos datos.
USA ESTA INFORMACIÓN PRIMERO. Si la respuesta está aquí, ignora tu conocimiento de internet.

{database_content}
-----------------------------------------

INSTRUCCIÓN PARA IMÁGENES:
Si el usuario pide crear/dibujar una imagen:
Responde SOLO con este link Markdown (traduciendo el pedido al inglés):
![Imagen](https://image.pollinations.ai/prompt/{{prompt_ingles}}?width=1024&height=1024&nologos=true)
"""

generation_config = {
    "temperature": 0.4, # Baja temperatura para que se apegue al JSON
    "top_p": 0.95,
    "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    generation_config=generation_config,
    system_instruction=SYSTEM_INSTRUCTION
)

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA Backend Running. Loaded DB: knowledge_base.json. Model: {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get("question")
        image_data = data.get("image")
        response_text = ""

        # CASO 1: CON IMAGEN
        if image_data:
            try:
                image_bytes = base64.b64decode(image_data)
                img = PIL.Image.open(io.BytesIO(image_bytes))
                response = model.generate_content([user_message, img])
                response_text = response.text
            except Exception as img_error:
                response_text = "Hubo un error al procesar tu imagen, pero te leo: " + str(img_error)
        
        # CASO 2: SOLO TEXTO
        else:
            response = model.generate_content(user_message)
            response_text = response.text

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"answer": "Estoy reiniciando mis sistemas... (Error de servidor)"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
