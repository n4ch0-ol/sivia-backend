import os
import json
import requests # <--- Usamos peticiones directas
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ ERROR: Falta la API KEY")

# 2. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 3. CONFIGURACIÓN MANUAL (SIN LIBRERÍAS)
# Usamos la URL directa de la API v1beta.
MODEL_NAME = "gemini-1.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"

SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES ---
{database_content}
REGLA: Responde de forma útil y breve.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA (MODO HTTP DIRECTO) - ONLINE"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image") # Base64 string

        # Construimos el cuerpo del mensaje (JSON) A MANO
        # Esto evita que ninguna librería meta la pata.
        
        parts = []
        
        # 1. Instrucción del sistema (simulada como primer mensaje de usuario para simplificar en HTTP puro)
        # Ojo: La API REST permite system_instruction, pero para asegurar compatibilidad máxima
        # lo ponemos como contexto en el mensaje.
        full_prompt = f"{SYSTEM_INSTRUCTION}\n\nPREGUNTA DEL USUARIO: {user_msg}"
        
        # 2. Si hay imagen, la agregamos
        if img_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })
        
        # 3. Agregamos el texto
        parts.append({"text": full_prompt})

        # Payload final
        payload = {
            "contents": [{
                "parts": parts
            }],
            # Configuración de generación
            "generationConfig": {
                "temperature": 0.4
            }
        }

        # === EL ENVÍO REAL ===
        print("📤 Enviando petición HTTP directa a Google...")
        response = requests.post(
            API_URL, 
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30 # 30 segundos de espera máximo
        )

        # Verificamos si Google respondió bien (Código 200)
        if response.status_code != 200:
            print(f"❌ ERROR HTTP {response.status_code}: {response.text}")
            return jsonify({"answer": f"Error de Google ({response.status_code}): {response.text}"}), 500

        # Procesamos la respuesta JSON pura
        result_json = response.json()
        
        try:
            # Intentamos sacar el texto
            answer = result_json['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except (KeyError, IndexError):
            # Si la estructura es rara (ej. filtro de seguridad)
            print(f"⚠️ Respuesta inesperada: {result_json}")
            return jsonify({"answer": "No pude generar una respuesta (posible filtro de seguridad)."}), 200

    except Exception as e:
        print(f"❌ ERROR INTERNO: {e}")
        return jsonify({"answer": f"Error del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
