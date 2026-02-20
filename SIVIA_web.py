import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 2. CONFIGURACIÓN DEL MODELO
# Usamos gemini-3-flash como solicitó el usuario
MODEL_NAME = "gemini-3-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"

# 3. BASE DE DATOS LOCAL
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 4. INSTRUCCIONES CON LOS FILTROS QUE PEDISTE
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.

--- REGLAS DE BÚSQUEDA ---
1. Tienes la herramienta Google Search. ÚSALA para datos actuales (noticias, política, clima, etc.).
2. FILTROS DE FUENTES:
   - Prioriza resultados de dominios: .edu, .gob, .org.
   - Si la información viene de fuentes no oficiales, verifícala dos veces o indica que es un rumor.
3. Si te preguntan sobre el "Centro de Estudiantes", usa PRIMERO los DATOS LOCALES.

--- DATOS LOCALES ---
{database_content}

Responde de forma concisa.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE - {MODEL_NAME} (Search Enabled)"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"answer": "Petición no válida (no se recibió JSON)."}), 400

        user_msg = data.get("question")
        img_data = data.get("image")

        if not user_msg:
            return jsonify({"answer": "Por favor, escribe una pregunta."}), 400

        # Preparamos las partes del contenido (mensaje del usuario)
        user_parts = [{"text": user_msg}]
        if img_data:
            user_parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })

        # Configuración de seguridad para evitar bloqueos innecesarios por "falsos positivos"
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
        ]

        # INTENTO 1: CON BÚSQUEDA (GROUNDING)
        # Nota: Usamos google_search que es el estándar actual
        payload_search = {
            "contents": [{"parts": user_parts}],
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "tools": [{"google_search": {}}],
            "safetySettings": safety_settings
        }

        print(f"📡 Consultando a {MODEL_NAME} con búsqueda...")
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json=payload_search,
            timeout=40
        )

        # Fallback si falla la búsqueda (ej. por cuota, error de herramienta o modelo)
        if response.status_code != 200:
            print(f"⚠️ Error en búsqueda ({response.status_code}): {response.text}")
            print("🔄 Reintentando en modo simple (sin búsqueda)...")

            payload_simple = {
                "contents": [{"parts": user_parts}],
                "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "safetySettings": safety_settings
            }
            response = requests.post(
                API_URL,
                headers={'Content-Type': 'application/json'},
                json=payload_simple,
                timeout=30
            )

        if response.status_code != 200:
            print(f"❌ Error API ({response.status_code}): {response.text}")
            # Intentamos dar un mensaje más útil basado en el error
            try:
                err_data = response.json()
                msg = err_data.get('error', {}).get('message', 'Error desconocido')
                return jsonify({"answer": f"Google API Error: {msg} ({response.status_code})"})
            except:
                return jsonify({"answer": f"Error del servidor de Google ({response.status_code})."})

        # PROCESAR RESPUESTA
        result = response.json()
        try:
            # Extraemos la respuesta de texto
            # Verificamos si hay candidatos y contenido
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    answer = candidate['content']['parts'][0]['text']
                    return jsonify({"answer": answer})

            # Si llegamos aquí, es que no hubo texto (posible bloqueo por seguridad)
            print(f"⚠️ Respuesta sin texto. Result: {result}")
            return jsonify({"answer": "Lo siento, la IA no pudo generar una respuesta. Puede que el tema esté restringido por seguridad."})

        except (KeyError, IndexError, TypeError) as e:
            print(f"Error procesando JSON: {e} | Respuesta completa: {result}")
            return jsonify({"answer": "Hubo un problema al leer la respuesta de la IA. Por favor, intenta de nuevo."})

    except Exception as e:
        print(f"❌ ERROR SERVIDOR: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
