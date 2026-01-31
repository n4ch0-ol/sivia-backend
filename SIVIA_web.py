import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Configuración de logs para que escupa TODO
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
load_dotenv()

app = Flask(__name__)
CORS(app)

# 1. VERIFICACIÓN DE API KEY AL INICIO
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logging.critical("¡¡¡NO SE ENCONTRÓ LA GOOGLE_API_KEY!!! Revisá las variables de entorno en Render.")
else:
    # Imprime los primeros 5 caracteres para confirmar que cargó algo (sin mostrarla toda)
    logging.info(f"API Key cargada: {GOOGLE_API_KEY[:5]}... (Longitud: {len(GOOGLE_API_KEY)})")
    genai.configure(api_key=GOOGLE_API_KEY)

# Modelo directo, sin vueltas
model = genai.GenerativeModel("gemini-1.5-flash")

@app.route("/chat", methods=['POST'])
def chat():
    logging.info("--> Recibida petición en /chat")
    
    try:
        data = request.json
        if not data:
            return jsonify({"answer": "Error: No llegaron datos JSON"}), 400

        user_question = data.get("question", "")
        logging.info(f"Pregunta recibida: {user_question}")

        # PRUEBA DE CONEXIÓN DIRECTA
        # Si esto falla, le mandamos el error crudo al frontend
        response = model.generate_content(user_question)
        
        logging.info("Respuesta generada con éxito")
        return jsonify({"answer": response.text})

    except Exception as e:
        # AQUÍ ESTÁ LA CLAVE: Devolvemos el error real al chat
        error_real = str(e)
        logging.exception("CRASH EN GEMINI:") # Esto imprime el traceback completo en logs
        
        # Mensaje visible en la pantalla de SIVIA
        mensaje_error = f"ERROR TÉCNICO REAL (Mándame esto): {error_real}"
        
        return jsonify({"answer": mensaje_error})

@app.route("/")
def home():
    # Chequeo rápido al entrar a la URL base
    key_status = "Cargada" if GOOGLE_API_KEY else "FALTANTE"
    return f"SIVIA Debug Mode. API Key: {key_status}. Logs activados."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
