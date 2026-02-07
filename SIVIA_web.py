import os
import json
import requests
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 1. CARGA DE VARIABLES
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 2. CONFIGURACIÓN
# Usamos gemini-1.5-flash que soporta herramientas de búsqueda y es rápido.
MODEL_NAME = "gemini-1.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"

# 3. BASE DE DATOS
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        database_content = json.dumps(data, indent=2, ensure_ascii=False)
except:
    database_content = "No hay datos específicos."

# 4. INSTRUCCIONES CON FILTRO DE DOMINIO
# Aquí le ordenamos que priorice los dominios que pediste.
SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.

--- TUS REGLAS DE BÚSQUEDA ---
1. Tienes acceso a Google Search. ÚSALO si la pregunta requiere información actual o externa.
2. FILTROS DE CALIDAD: Cuando busques información, PRIORIZA ABSOLUTAMENTE fuentes oficiales y académicas que terminen en:
   - .edu (Educación)
   - .gob / .gov (Gobierno)
   - .org (Organizaciones)
3. Si la información viene de un blog genérico o red social, verifícala o deséchala.
4. Si la pregunta es sobre el "Centro de Estudiantes" o "Manos Unidas", usa PRIMERO tu base de datos local.

--- BASE DE DATOS LOCAL ---
{database_content}

Responde de forma clara, útil y citando fuentes si buscaste en internet.
"""

@app.route('/', methods=['GET'])
def home():
    return f"SIVIA ONLINE ({MODEL_NAME}) - SEARCH ON"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_msg = data.get("question")
        img_data = data.get("image")

        parts = []
        # Inyectamos la instrucción como contexto
        parts.append({"text": f"{SYSTEM_INSTRUCTION}\n\nPREGUNTA DEL USUARIO: {user_msg}"})

        if img_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_data
                }
            })

        # === AQUÍ ESTÁ LA MAGIA ===
        # Agregamos la herramienta de búsqueda en el JSON manual
        payload = {
            "contents": [{"parts": parts}],
            "tools": [
                {"google_search": {}}  # <--- ESTO ACTIVA INTERNET
            ]
        }

        print(f"📡 Consultando a Google con Search activado...")
        response = requests.post(
            API_URL, 
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=40 # Damos un poco más de tiempo para la búsqueda
        )

        if response.status_code != 200:
            print(f"❌ Error Google: {response.text}")
            return jsonify({"answer": f"Error ({response.status_code}): No pude buscar en internet."})

        result = response.json()
        
        try:
            # Intentamos leer la respuesta
            # A veces la respuesta con búsqueda tiene una estructura compleja, buscamos el texto principal
            candidate = result['candidates'][0]
            answer = candidate['content']['parts'][0]['text']
            
            # (Opcional) Podríamos buscar si hay 'groundingMetadata' para ver los links, 
            # pero el modelo suele incluirlos en el texto si se lo pides.
            
            return jsonify({"answer": answer})
        except Exception as e:
            print(f"⚠️ Error parseando respuesta: {e}")
            return jsonify({"answer": "Encontré información pero no pude procesarla correctamente."})

    except Exception as e:
        print(f"❌ ERROR INTERNO: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
