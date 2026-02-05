import os
import base64
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 1. CARGA DE VARIABLES
load_dotenv()

app = Flask(__name__)
# Permitimos CORS para que tu frontend pueda hablar con este backend
CORS(app)

# 2. CONFIGURACIÓN DE LA LLAVE MAESTRA
# En Render, usa la variable: CREATY_API_KEY
API_KEY = os.getenv("CREATY_API_KEY")

if not API_KEY:
    print("❌ ERROR CRÍTICO: No se encontró la variable CREATY_API_KEY.")
else:
    genai.configure(api_key=API_KEY)

# 3. DEFINICIÓN DE MODELOS
TEXT_MODEL_NAME = "models/gemini-1.5-flash"
IMAGEN_MODEL_NAME = "models/imagen-3.0-generate-001"

# --- CONFIGURACIÓN DE LA PERSONALIDAD "VISTA" ---
# Esto hace que el modelo de texto SIEMPRE sepa quién es.
sistema_instrucciones = """
Tu nombre es Vista. 
Eres una asistente creativa, inteligente y amable del motor CREATY.
Tus respuestas son concisas y útiles.
Siempre te mantienes en personaje como "Vista".
"""

# Instanciamos el modelo de chat con la instrucción de sistema
chat_model = genai.GenerativeModel(
    model_name=TEXT_MODEL_NAME,
    system_instruction=sistema_instrucciones
)

print(f"🎨 INICIANDO MOTOR VISTA...")

# --- FUNCIÓN: GENERADOR DE IMÁGENES HÍBRIDO ---
def generar_arte(prompt_optimizado):
    try:
        print(f"🖌️ Intentando usar Google Imagen 3 con: {prompt_optimizado[:30]}...")
        imagen_model = genai.GenerativeModel(IMAGEN_MODEL_NAME)
        
        result = imagen_model.generate_images(
            prompt=prompt_optimizado,
            number_of_images=1,
            aspect_ratio="16:9", 
            safety_filter_level="block_only_high"
        )
        
        image_bytes = result.images[0].image_bytes
        b64_string = base64.b64encode(image_bytes).decode('utf-8')
        return f'<img src="data:image/jpeg;base64,{b64_string}" alt="Generado por Google Imagen 3" style="width:100%; border-radius:10px;">'

    except Exception as e:
        print(f"⚠️ Google Imagen 3 falló ({str(e)}). Activando Flux...")
        import urllib.parse
        safe_prompt = urllib.parse.quote(prompt_optimizado)
        return f'<img src="https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologos=true&model=flux" alt="Generado por Flux" style="width:100%; border-radius:10px;">'

# --- RUTA 1: HOME ---
@app.route('/', methods=['GET'])
def home():
    return "CREATY ENGINE ONLINE /// Soy Vista."

# --- RUTA 2: CHAT (NUEVO - Aquí es donde habla Vista) ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Iniciamos un chat (sin historial para hacerlo simple y rápido, o puedes agregar history)
        chat = chat_model.start_chat(history=[])
        response = chat.send_message(user_message)
        
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- RUTA 3: GENERAR IMÁGENES ---
@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        user_input = data.get("prompt", "")

        if not user_input:
            return jsonify({"result": "El lienzo necesita una idea."})

        # Usamos el modelo para mejorar el prompt
        prompt_instruction = f"""
        Actúa como un director de arte experto. 
        Transforma esta idea breve: "{user_input}" 
        en un PROMPT DETALLADO EN INGLÉS para una IA generativa.
        Solo devuelve el prompt en inglés.
        """
        response_prompt = chat_model.generate_content(prompt_instruction)
        enhanced_prompt = response_prompt.text.strip()
        
        # Generamos la imagen
        html_imagen = generar_arte(enhanced_prompt)
        
        # Generamos el título
        response_caption = chat_model.generate_content(
            f"Escribe un título muy breve y poético en español para: {user_input}"
        )
        caption = response_caption.text.strip()

        final_html = f"""
        <div class="artwork-wrapper">
            {html_imagen}
            <div class="caption">
                <strong>{caption}</strong><br>
                <span style="font-size:10px; color:#aaa;">Vista Engine</span>
            </div>
        </div>
        """
        return jsonify({"result": final_html})

    except Exception as e:
        return jsonify({"result": f"<p>Error: {str(e)}</p>"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
