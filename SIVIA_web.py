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
    print("ERROR FATAL: No se encontró la GOOGLE_API_KEY")
    
genai.configure(api_key=GOOGLE_API_KEY)

# --- SISTEMA DE AUTO-DETECCIÓN DE MODELO ---
# Esto evita el error 404. El código busca un modelo que SÍ exista.
def get_best_model():
    print("--- BUSCANDO MODELOS DISPONIBLES ---")
    valid_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
                print(f"Disponible: {m.name}")
    except Exception as e:
        print(f"Error listando modelos: {e}")
        # Si falla el listado, intentamos el clásico a ciegas
        return "models/gemini-pro"

    # Preferencias: Intentamos buscar estos en orden
    preferences = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro"]
    
    for pref in preferences:
        if pref in valid_models:
            return pref
    
    # Si no encuentra los preferidos, usa el primero que encontró
    if valid_models:
        return valid_models[0]
    
    return "models/gemini-pro" # Fallback final

# ELEGIMOS EL MODELO
MODEL_NAME = get_best_model()
print(f"--- SIVIA USARÁ EL MODELO: {MODEL_NAME} ---")

# --- INSTRUCCIÓN SIVIA ---
SYSTEM_INSTRUCTION = """
Eres SIVIA, una IA asistente útil y amable en español.

INSTRUCCIÓN DE IMÁGENES:
Si el usuario pide crear/dibujar una imagen, NO digas que no puedes.
Responde con este formato Markdown exacto:
![Imagen Generada](https://image.pollinations.ai/prompt/{descripcion_en_ingles}?width=1024&height=1024&nologos=true)
(Traduce el prompt del usuario al inglés para la URL).
"""

generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "max_output_tokens": 8192,
}

# Inicializar Modelo
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    generation_config=generation_config,
    system_instruction=SYSTEM_INSTRUCTION
)

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA Backend Running using {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get("question")
        image_data = data.get("image")

        response_text = ""

        if image_data:
            # Caso con Imagen
            try:
                image_bytes = base64.b64decode(image_data)
                img = PIL.Image.open(io.BytesIO(image_bytes))
                response = model.generate_content([user_message, img])
                response_text = response.text
            except Exception as img_error:
                response_text = "Recibí la imagen, pero hubo un error procesándola. Intenta solo texto."
                print(f"Error imagen: {img_error}")
        else:
            # Caso solo Texto
            response = model.generate_content(user_message)
            response_text = response.text

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"ERROR GENERAL: {e}")
        return jsonify({"answer": "Lo siento, estoy teniendo un problema de conexión con mi cerebro (API Error)."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
