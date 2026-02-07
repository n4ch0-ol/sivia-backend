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
# Usamos el nombre EXACTO que apareció en tu lista.
MODEL_NAME = "gemini-flash-latest"
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
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        parts = [{"text": f"{SYSTEM_INSTRUCTION}\n\nUsuario: {user_msg}"}]

        if img_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })

        # INTENTO 1: CON BÚSQUEDA (INTERNET)
        payload_search = {
            "contents": [{"parts": parts}],
            "tools": [{"google_search": {}}]  # Activamos Google Search
        }

        print(f"📡 Buscando en internet con {MODEL_NAME}...")
        response = requests.post(
            API_URL, 
            headers={'Content-Type': 'application/json'},
            json=payload_search,
            timeout=40
        )

        # Si falla (ej: el modelo no soporta búsqueda o da 404), intentamos sin búsqueda
        if response.status_code != 200:
            print(f"⚠️ Falló la búsqueda ({response.status_code}). Reintentando sin internet...")
            
            # INTENTO 2: SIN BÚSQUEDA (MODO SEGURO)
            payload_simple = {"contents": [{"parts": parts}]}
            response = requests.post(
                API_URL, 
                headers={'Content-Type': 'application/json'},
                json=payload_simple,
                timeout=30
            )

            if response.status_code != 200:
                 return jsonify({"answer": f"Error total ({response.status_code}): {response.text}"})

        # PROCESAR RESPUESTA
        result = response.json()
        try:
            # Buscamos el texto en la respuesta
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"answer": answer})
        except Exception as e:
            # A veces la respuesta viene vacía si hubo un filtro de seguridad
            print(f"Error leyendo JSON: {e}")
            return jsonify({"answer": "Lo siento, encontré información pero no pude leerla correctamente."})

    except Exception as e:
        print(f"❌ ERROR SERVIDOR: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
