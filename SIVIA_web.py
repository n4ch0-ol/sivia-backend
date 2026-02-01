import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64

# Cargar variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurar API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("ERROR: No se encontró la GOOGLE_API_KEY")
    
genai.configure(api_key=GOOGLE_API_KEY)

# --- DIAGNÓSTICO: VER QUÉ MODELOS HAY DISPONIBLES ---
print("--- BUSCANDO MODELOS DISPONIBLES ---")
try:
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Modelo encontrado: {m.name}")
            available_models.append(m.name)
except Exception as e:
    print(f"Error listando modelos: {e}")
print("----------------------------------------")

# --- INSTRUCCIÓN PARA IMÁGENES ---
SYSTEM_INSTRUCTION = """
Eres SIVIA, una IA asistente útil y amable en español.

SI EL USUARIO PIDE UNA IMAGEN:
Genera un enlace Markdown a Pollinations.
Ejemplo: ![Imagen](https://image.pollinations.ai/prompt/{descripcion_ingles}?width=1024&height=1024&nologos=true)
"""

# INTENTAMOS USAR EL NOMBRE MÁS ESTABLE
# Si falla, miraremos los logs para ver cuál está disponible
MODEL_NAME = "gemini-1.5-flash-latest" 

generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "max_output_tokens": 8192,
}

# Variable global para el modelo
model = None

try:
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config=generation_config,
        system_instruction=SYSTEM_INSTRUCTION
    )
    print(f"--- SIVIA LISTA USANDO: {MODEL_NAME} ---")
except Exception as e:
    print(f"--- ERROR INICIALIZANDO {MODEL_NAME}: {e} ---")
    print("Intentando fallback a 'gemini-pro'...")
    try:
        model = genai.GenerativeModel("gemini-pro") # Fallback de emergencia
        print("--- FALLBACK A GEMINI-PRO EXITOSO ---")
    except Exception as e2:
         print(f"--- ERROR FATAL: {e2} ---")

@app.route('/', methods=['GET'])
def home():
    return "SIVIA Backend Running"

@app.route('/chat', methods=['POST'])
def chat():
    global model
    try:
        if not model:
            return jsonify({"answer": "Error: El modelo IA no está cargado."}), 500

        data = request.json
        user_message = data.get("question")
        image_data = data.get("image")

        response_text = ""

        # CASO CON IMAGEN
        if image_data:
            image_bytes = base64.b64decode(image_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            response = model.generate_content([user_message, img])
            response_text = response.text
        
        # CASO SOLO TEXTO
        else:
            response = model.generate_content(user_message)
            response_text = response.text

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"ERROR EN CHAT: {e}")
        return jsonify({"answer": f"Ocurrió un error en el servidor: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
