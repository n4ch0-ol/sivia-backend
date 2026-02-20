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

# 2. LISTA DE MODELOS A PROBAR (Orden de prioridad)
MODELS_TO_TRY = [
    "gemini-3-flash",
    "gemini-3.0-flash",
    "gemini-3.1-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.5-flash",
    "gemini-2-flash",
    "gemini-3",
    "gemini-3.0",
    "gemini-3.1",
    "gemini-2.0",
    "gemini-1.5",
    "gemini-2.5",
    "gemini-2"
]

# 3. BASE DE DATOS LOCAL
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 4. INSTRUCCIONES DEL SISTEMA
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
    return f"SIVIA ONLINE - Multimodel Fallback Enabled"

@app.route('/chat', methods=['POST'])
def chat():
    if not GOOGLE_API_KEY:
        return jsonify({"answer": "Error: Falta GOOGLE_API_KEY"}), 500

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"answer": "Petición no válida (no se recibió JSON)."}), 400

        user_msg = data.get("question")
        img_data = data.get("image")

        if not user_msg:
            return jsonify({"answer": "Por favor, escribe una pregunta."}), 400

        user_parts = [{"text": user_msg}]
        if img_data:
            user_parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
        ]

        last_error = ""

        # Bucle para probar diferentes modelos
        for model_name in MODELS_TO_TRY:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GOOGLE_API_KEY}"

            # Intentamos con BÚSQUEDA primero
            payloads = [
                {
                    "name": "Búsqueda Web",
                    "json": {
                        "contents": [{"parts": user_parts}],
                        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                        "tools": [{"google_search": {}}],
                        "safetySettings": safety_settings
                    }
                },
                {
                    "name": "Modo Simple",
                    "json": {
                        "contents": [{"parts": user_parts}],
                        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                        "safetySettings": safety_settings
                    }
                }
            ]

            for p in payloads:
                try:
                    print(f"📡 Probando modelo {model_name} ({p['name']})...")
                    response = requests.post(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        json=p['json'],
                        timeout=35
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if 'candidates' in result and len(result['candidates']) > 0:
                            candidate = result['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                answer = candidate['content']['parts'][0]['text']
                                return jsonify({"answer": answer, "model": model_name})

                        print(f"⚠️ {model_name} respondió sin texto (posible filtro).")
                    elif response.status_code == 404:
                        print(f"🚫 El modelo {model_name} no existe (404). Saltando...")
                        break # Salta al siguiente modelo de MODELS_TO_TRY
                    else:
                        print(f"❌ {model_name} falló con código {response.status_code}.")
                        last_error = f"Google API ({model_name}): {response.text}"

                except Exception as e:
                    print(f"❗ Error de conexión con {model_name}: {e}")
                    last_error = str(e)

            # Si el código llega aquí, este modelo no funcionó, pasamos al siguiente

        return jsonify({
            "answer": "Lo siento, todos los modelos disponibles están fallando o han agotado su cuota. Por favor, intenta de nuevo en unos minutos.",
            "details": last_error
        })

    except Exception as e:
        print(f"❌ ERROR SERVIDOR: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
