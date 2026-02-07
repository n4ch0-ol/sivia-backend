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
    print("❌ ERROR: No hay API KEY")

# 2. CONFIGURACIÓN SIMPLE (LA CLÁSICA)
genai.configure(api_key=GOOGLE_API_KEY)

# 3. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Responde basándote en los datos locales.
"""

# 4. EL MODELO QUE SIEMPRE FUNCIONA
# Si este falla, es porque Render tiene basura en el caché.
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_INSTRUCTION
)

@app.route('/', methods=['GET'])
def home():
    return "SIVIA ONLINE (V. CLÁSICA)"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        # MODO SIMPLE: Texto o Imagen+Texto
        if img_data:
            image_bytes = base64.b64decode(img_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            response = model.generate_content([user_msg, img])
        else:
            response = model.generate_content(user_msg)

        return jsonify({"answer": response.text})

    except Exception as e:
        # Si falla aquí, imprimimos el error real para verlo
        print(f"❌ ERROR: {e}")
        return jsonify({"answer": "Error al procesar la respuesta."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
