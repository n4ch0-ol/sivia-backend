import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import PIL.Image
import io
import base64
import sys # Para forzar la impresión de logs

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR CRÍTICO: No se encontró la GOOGLE_API_KEY en las variables de entorno.", file=sys.stderr)

# Configuración de Google
genai.configure(api_key=GOOGLE_API_KEY)

# 2. BASE DE DATOS LOCAL
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except Exception as e:
    print(f"⚠️ Advertencia: No se cargó la base de datos ({e})", file=sys.stderr)
    database_content = "No hay datos específicos cargados."

# 3. INSTRUCCIONES
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Responde basándote en los datos locales. Sé amable y breve.
"""

# 4. MODELO - AQUÍ ESTÁ EL CAMBIO CLAVE
# Usamos 'gemini-2.0-flash' porque vimos en tus logs que ESTE es el que tienes activo.
MODEL_NAME = "gemini-2.0-flash"

try:
    print(f"🔄 Iniciando modelo {MODEL_NAME}...", file=sys.stdout)
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION
    )
    print("✅ Modelo cargado correctamente.", file=sys.stdout)
except Exception as e:
    print(f"❌ ERROR AL CARGAR MODELO: {e}", file=sys.stderr)
    model = None

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - Modelo: {MODEL_NAME}"

@app.route('/chat', methods=['POST'])
def chat():
    print("📩 Recibida petición en /chat", file=sys.stdout)
    
    if not model:
        print("❌ El modelo es None. Abortando.", file=sys.stderr)
        return jsonify({"answer": "Error crítico: El cerebro de SIVIA no arrancó."}), 500

    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        print(f"👤 Usuario pregunta: {user_msg}", file=sys.stdout)

        if img_data:
            # === CASO CON IMAGEN ===
            print("🖼️ Procesando imagen...", file=sys.stdout)
            try:
                image_bytes = base64.b64decode(img_data)
                img = PIL.Image.open(io.BytesIO(image_bytes))
                response = model.generate_content([user_msg, img])
                print("✅ Respuesta generada con imagen.", file=sys.stdout)
                return jsonify({"answer": response.text})
            except Exception as e_img:
                print(f"❌ Error procesando imagen: {e_img}", file=sys.stderr)
                return jsonify({"answer": "Hubo un problema viendo la imagen."})
            
        else:
            # === CASO SOLO TEXTO ===
            print("📝 Generando texto...", file=sys.stdout)
            response = model.generate_content(user_msg)
            
            # Verificamos si la respuesta está bloqueada por seguridad
            if not response.text and response.prompt_feedback:
                 print(f"⚠️ Bloqueo de seguridad: {response.prompt_feedback}", file=sys.stderr)
                 return jsonify({"answer": "No puedo responder a eso por motivos de seguridad."})

            print("✅ Respuesta enviada.", file=sys.stdout)
            return jsonify({"answer": response.text})

    except Exception as e:
        # ESTE ES EL ERROR QUE NO VEÍAS ANTES
        print(f"❌ ERROR FATAL EN CHAT: {str(e)}", file=sys.stderr)
        # Devolvemos el error real al frontend para que lo veas en pantalla si quieres
        return jsonify({"answer": f"Error interno: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
