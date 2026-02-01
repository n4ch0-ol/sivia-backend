import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app)  # Permite que tu HTML hable con este servidor

# Configurar API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# --- AQUÍ ESTÁ EL TRUCO PARA LAS IMÁGENES ---
# Le damos una "personalidad" e instrucciones estrictas
SYSTEM_INSTRUCTION = """
Eres SIVIA, una IA asistente avanzada y útil.
Tus respuestas deben ser claras, amables y en español.

IMPORTANTE - GENERACIÓN DE IMÁGENES:
Si el usuario te pide "crear", "generar", "dibujar" o "hacer" una imagen, foto o dibujo:
1. NO digas que eres un modelo de lenguaje y que no puedes.
2. SÍ PUEDES hacerlo generando un enlace especial.
3. Para generar la imagen, responde EXCLUSIVAMENTE con este formato de enlace Markdown:
   ![Imagen generada](https://image.pollinations.ai/prompt/{descripcion_en_ingles}?width=1024&height=1024&nologos=true)
   
   (Debes traducir la petición del usuario a inglés para ponerla dentro de {descripcion_en_ingles}).

Ejemplo:
Usuario: "Dibuja un gato futurista neon"
Tú: "Aquí tienes tu imagen: ![Gato](https://image.pollinations.ai/prompt/futuristic%20neon%20cat?width=1024&height=1024&nologos=true)"
"""

# Configuración del modelo con las instrucciones
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=SYSTEM_INSTRUCTION # <--- Esto inyecta la instrucción
)

chat_session = model.start_chat(history=[])

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get("question")
        image_data = data.get("image") # Base64 si el usuario sube foto

        response_text = ""

        # CASO 1: El usuario manda texto + imagen
        if image_data:
            import PIL.Image
            import io
            import base64
            
            # Decodificar imagen
            image_bytes = base64.b64decode(image_data)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            # Enviar a Gemini Vision
            response = model.generate_content([user_message, img])
            response_text = response.text

        # CASO 2: Solo texto (aquí es donde puede pedir generar imagen)
        else:
            response = chat_session.send_message(user_message)
            response_text = response.text

        return jsonify({"answer": response_text})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"answer": "Lo siento, tuve un error interno."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
