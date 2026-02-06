import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64


import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64

# 1. CARGAR VARIABLES DE ENTORNO (Lo primero de todo)
load_dotenv()

app = Flask(__name__)
CORS(app)

# 2. CONFIGURAR API KEY (Necesario antes de usar herramientas)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("ERROR FATAL: No se encontró la GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# ==========================================
# 3. CONFIGURACIÓN DE HERRAMIENTAS (CORREGIDO)
# ==========================================
# Definimos la herramienta con la sintaxis segura 'protos'
tools_sivia = [
    genai.protos.Tool(
        google_search_retrieval=genai.protos.GoogleSearchRetrieval()
    )
]

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
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
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

    # Priorizamos Flash o Pro (ambos soportan búsqueda)
    preferences = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro"]
    for pref in preferences:
        if pref in valid_models:
            return pref
    
    if valid_models: return valid_models[0]
    return "models/gemini-pro"

MODEL_NAME = get_best_model()
print(f"--- SIVIA USARÁ EL MODELO: {MODEL_NAME} ---")

# ==========================================
# 3. CONFIGURACIÓN DE HERRAMIENTAS (¡LA SOLUCIÓN!)
# ==========================================
# Aquí activamos el buscador de Google para Sivia
tools_sivia = [
    {"google_search": {}} 
]

# ==========================================
# 4. INSTRUCCIONES DEL CEREBRO (SIVIA)
# ==========================================
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA oficial del Centro de Estudiantes "Manos Unidas".
Tu personalidad es útil, joven, empática y clara.

--- TU CONOCIMIENTO REAL (IMPORTANTE) ---
Toda la verdad sobre horarios, materias, precios y quiénes somos está en estos datos locales:
{database_content}

REGLA DE ORO PARA RESPONDER:
1. PRIMERO verifica si la respuesta está en los datos locales de arriba. Si está ahí, responde con eso y NO busques en internet.
2. Si la respuesta NO está en los datos locales (por ejemplo, clima, noticias actuales, hechos generales, preguntas de estudio), ENTONCES usa tu herramienta de Búsqueda de Google para encontrar la respuesta actualizada.

INSTRUCCIÓN PARA IMÁGENES:
Si el usuario pide crear/dibujar una imagen:
Responde SOLO con este link Markdown (traduciendo el pedido al inglés):
![Imagen](https://image.pollinations.ai/prompt/{{prompt_ingles}}?width=1024&height=1024&nologos=true)
"""

generation_config = {
    "temperature": 0.4,
    "top_p": 0.95,
    "max_output_tokens": 8192,
}

# Inicializamos el modelo CON LAS TOOLS (Aquí estaba el faltante)
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    generation_config=generation_config,
    system_instruction=SYSTEM_INSTRUCTION,
    tools=tools_sivia  # <--- ESTA LÍNEA ACTIVA EL INTERNET
)

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA Backend Running. Loaded DB: knowledge_base.json. Model: {MODEL_NAME} (Search Enabled)"

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
                # Nota: Gemini a veces desactiva la búsqueda si hay imágenes, 
                # pero intentará procesarlo igual.
                response = model.generate_content([user_message, img])
                response_text = response.text
            except Exception as img_error:
                response_text = "Hubo un error al procesar tu imagen, pero te leo: " + str(img_error)
        
        # CASO 2: SOLO TEXTO (Aquí brillará la búsqueda)
        else:
            response = model.generate_content(user_message)
            
            # Verificamos si la respuesta viene por partes (común cuando usa herramientas)
            if response.parts:
                response_text = response.text
            else:
                # Fallback por si la estructura cambia
                response_text = response.text

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"answer": "Estoy reiniciando mis sistemas... (Error de servidor)"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


