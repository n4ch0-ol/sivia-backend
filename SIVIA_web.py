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

# Configuración de Google
genai.configure(api_key=GOOGLE_API_KEY)

# 2. BASE DE DATOS LOCAL
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
REGLA: Responde basándote en los datos locales. Si no sabes, dilo amablemente.
"""

# 4. MODELO (Versión Estándar)
# Usamos 'gemini-1.5-flash' que es el estándar gratuito.
# Si este te falla, cambia el nombre a "gemini-2.0-flash" que vimos en tu lista.
try:
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_INSTRUCTION
    )
    print("✅ Modelo SIVIA cargado correctamente.")
except Exception as e:
    print(f"❌ Error cargando modelo: {e}")
    model = None

@app.route('/', methods=['GET'])
def home():
    return "SIVIA (Classic) - ONLINE"

@app.route('/chat', methods=['POST'])
def chat():
    if not model:
        return jsonify({"answer": "Error: El modelo no está activo."}), 500

    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        if img_data:
            # === CASO CON IMAGEN ===
            try:
                image_bytes = base64.b64decode(img_data)
                img = PIL.Image.open(io.BytesIO(image_bytes))
                response = model.generate_content([user_msg, img])
                return jsonify({"answer": response.text})
            except Exception as e:
                print(f"Error imagen: {e}")
                return jsonify({"answer": "Hubo un problema procesando la imagen."})
            
        else:
            # === CASO SOLO TEXTO ===
            response = model.generate_content(user_msg)
            return jsonify({"answer": response.text})

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"answer": "Ocurrió un error al procesar tu mensaje."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
