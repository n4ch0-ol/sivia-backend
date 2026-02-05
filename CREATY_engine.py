import os
import time
import base64
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 1. CARGA DE VARIABLES
load_dotenv()

app = Flask(__name__)
CORS(app)

# 2. CONFIGURACIÓN DE LA LLAVE MAESTRA
CREATY_API_KEY = os.getenv("CREATY_API_KEY")

if not CREATY_API_KEY:
    print("❌ ERROR CRÍTICO: No se encontró la variable CREATY_API_KEY.")
else:
    genai.configure(api_key=CREATY_API_KEY)

# 3. DEFINICIÓN DE MODELOS
# Usamos Flash para el cerebro (rápido y gratis)
CREATY_TEXT_MODEL_NAME = "gemini-1.5-flash"
# Usamos Imagen 3 para el arte
CREATY_IMAGE_MODEL_NAME = "models/imagen-3.0-generate-001"

print(f"🎨 CONFIGURACIÓN: Vista Engine (Modo Solo Imágenes)")

# --- PERSONALIDAD VISTA ---
sistema_instrucciones_vista = """
Tu nombre es Vista. 
Eres una asistente creativa del motor CREATY especializada exclusivamente en arte visual estático.
Tu función es ayudar a crear imágenes increíbles.
Tus respuestas son concisas y útiles. Siempre te presentas como Vista.
Si el usuario pide video, aclara amablemente que tu especialidad es la fotografía y la ilustración.
"""

# Instanciamos el modelo de chat
try:
    chat_model = genai.GenerativeModel(
        model_name=CREATY_TEXT_MODEL_NAME,
        system_instruction=sistema_instrucciones_vista
    )
    print(f"✅ CEREBRO DE VISTA INICIADO")
except Exception as e:
    print(f"❌ Error fatal iniciando chat_model: {e}")

# --- FUNCIÓN: GENERADOR DE IMÁGENES ---
def generar_imagen(prompt_optimizado):
    try:
        print(f"🖌️ Generando con Imagen 3: {prompt_optimizado[:40]}...")
        imagen_model = genai.GenerativeModel(CREATY_IMAGE_MODEL_NAME)
        
        result = imagen_model.generate_images(
            prompt=prompt_optimizado,
            number_of_images=1,
            aspect_ratio="16:9", 
            safety_filter_level="block_only_high"
        )
        
        image_bytes = result.images[0].image_bytes
        b64_string = base64.b64encode(image_bytes).decode('utf-8')
        return f'<img src="data:image/jpeg;base64,{b64_string}" alt="Arte por Vista" style="width:100%; border-radius:10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">'

    except Exception as e:
        print(f"⚠️ Imagen 3 falló ({e}). Usando Flux...")
        import urllib.parse
        safe_prompt = urllib.parse.quote(prompt_optimizado)
        return f'<img src="https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologos=true&model=flux" alt="Arte por Flux" style="width:100%; border-radius:10px;">'

# --- RUTAS ---

@app.route('/', methods=['GET'])
def home():
    return "CREATY ENGINE ONLINE /// Vista Image Generator Ready."

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        chat_session = chat_model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        
        return jsonify({"response": response.text})
    except Exception as e:
        if "429" in str(e):
            return jsonify({"response": "Estoy creando mucho arte ahora mismo. Dame unos segundos..."})
        return jsonify({"error": str(e)}), 500

@app.route('/generate_art', methods=['POST']) 
def generate_art():
    try:
        data = request.json
        user_input = data.get("prompt", "")
        # Ignoramos el 'type' porque ahora SOLO hacemos imágenes

        if not user_input:
            return jsonify({"result": "El lienzo necesita una idea."})

        # 1. Mejorar Prompt
        prompt_instruction = f"""
        Actúa como un fotógrafo experto. 
        Transforma: "{user_input}" 
        en un PROMPT VISUAL EN INGLÉS detallado. Estilo cinemático, 8k.
        Solo devuelve el prompt en inglés.
        """
        response_prompt = chat_model.generate_content(prompt_instruction)
        enhanced_prompt = response_prompt.text.strip()
        
        # 2. Generar Imagen
        html_art = generar_imagen(enhanced_prompt)
        
        # 3. Título
        try:
            response_caption = chat_model.generate_content(
                f"Un título de 3 palabras, poético y en español para: {user_input}"
            )
            caption = response_caption.text.strip()
        except:
            caption = "Vista Art"

        # 4. Resultado
        final_html = f"""
        <div class="artwork-wrapper">
            {html_art}
            <div class="caption" style="margin-top:10px;">
                <strong>{caption}</strong><br>
                <span style="font-size:10px; color:#aaa;">Vista Image Engine</span>
            </div>
        </div>
        """
        return jsonify({"result": final_html})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"result": f"<p style='color:red;'>Error creando imagen: {str(e)}</p>"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
