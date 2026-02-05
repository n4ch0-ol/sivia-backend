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
# Permitimos CORS para que tu frontend pueda hablar con este backend
CORS(app)

# 2. CONFIGURACIÓN DE LA LLAVE MAESTRA
# En Render, debes crear la variable de entorno: CREATY_API_KEY
CREATY_API_KEY = os.getenv("CREATY_API_KEY")

if not CREATY_API_KEY:
    print("❌ ERROR CRÍTICO: No se encontró la variable CREATY_API_KEY.")
else:
    genai.configure(api_key=CREATY_API_KEY)

# 3. DEFINICIÓN DE MODELOS
CREATY_TEXT_MODEL_NAME = "models/gemini-1.5-flash"
CREATY_IMAGE_MODEL_NAME = "models/imagen-3.0-generate-001"
# OJO: Veo es 'alpha' y puede no estar disponible para todas las cuentas o regiones
CREATY_VIDEO_MODEL_NAME = "models/veo-001" 

# --- CONFIGURACIÓN DE LA PERSONALIDAD "VISTA" ---
# Esto hace que el modelo de texto SIEMPRE sepa quién es.
sistema_instrucciones_vista = """
Tu nombre es Vista. 
Eres una asistente creativa, inteligente y amable del motor CREATY.
Tu principal función es ayudar a los usuarios a generar imágenes y videos.
Cuando generas imágenes o videos, indicas que estás usando el "motor de Vista".
Tus respuestas son concisas, útiles y siempre te mantienes en personaje como "Vista".
Si el usuario pide una imagen o video, enfócate en pedir detalles para el prompt.
"""

# Instanciamos el modelo de chat con la instrucción de sistema
chat_model = genai.GenerativeModel(
    model_name=CREATY_TEXT_MODEL_NAME,
    system_instruction=sistema_instrucciones_vista
)

print(f"🎨 INICIANDO MOTOR VISTA (con soporte para imagen y video)...")

# --- FUNCIÓN: GENERADOR DE IMÁGENES HÍBRIDO ---
def generar_imagen(prompt_optimizado):
    try:
        print(f"🖌️ Intentando usar Google Imagen 3 con: {prompt_optimizado[:50]}...")
        imagen_model = genai.GenerativeModel(CREATY_IMAGE_MODEL_NAME)
        
        result = imagen_model.generate_images(
            prompt=prompt_optimizado,
            number_of_images=1,
            aspect_ratio="16:9", 
            safety_filter_level="block_only_high"
        )
        
        image_bytes = result.images[0].image_bytes
        b64_string = base64.b64encode(image_bytes).decode('utf-8')
        return f'<img src="data:image/jpeg;base64,{b64_string}" alt="Imagen generada por Vista (Imagen 3)" style="width:100%; border-radius:10px;">'

    except Exception as e:
        print(f"⚠️ Google Imagen 3 falló o no tiene permiso ({str(e)}). Activando Flux...")
        import urllib.parse
        safe_prompt = urllib.parse.quote(prompt_optimizado)
        return f'<img src="https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologos=true&model=flux" alt="Imagen generada por Vista (Flux)" style="width:100%; border-radius:10px;">'

# --- FUNCIÓN: GENERADOR DE VIDEO (con Veo) ---
def generar_video(prompt_optimizado):
    try:
        print(f"🎥 Intentando usar Google Veo con: {prompt_optimizado[:50]}...")
        video_model = genai.GenerativeModel(CREATY_VIDEO_MODEL_NAME)
        
        # OJO: La duración del video y otros parámetros pueden ser limitados por la API
        # y la cuota de uso. Veo es más lento.
        result = video_model.generate_videos(
            prompt=prompt_optimizado,
            number_of_videos=1,
            video_length_seconds=4, # Máximo 4 segundos para empezar
            aspect_ratio="16:9", 
            safety_filter_level="block_only_high"
        )
        
        # Veo devuelve un objeto VideoFile. Necesitamos la URL.
        # Esto puede tardar varios segundos (o minutos) en estar listo.
        # NO es instantáneo como las imágenes.
        video_uri = result.videos[0].uri 
        
        # NOTA IMPORTANTE: Para que esto funcione en tu frontend, necesitarás un 
        # cliente que pueda manejar la URL del video y tal vez un loader.
        # Aquí solo devolvemos la URL dentro de un tag de video.
        return f'<video controls loop autoplay src="{video_uri}" alt="Video generado por Vista (Veo)" style="width:100%; border-radius:10px;"></video>'

    except Exception as e:
        print(f"❌ Error al generar video con Veo ({str(e)}). Veo puede no estar disponible o tener límites.")
        # No hay un fallback fácil para video como con las imágenes.
        return f'<p style="color:red;">Lo siento, Vista no pudo generar el video con Veo. Error: {str(e)}</p>'


# --- RUTA 1: HOME ---
@app.route('/', methods=['GET'])
def home():
    return "CREATY ENGINE ONLINE /// Soy Vista, lista para crear."

# --- RUTA 2: CHAT (El Cerebro de Vista) ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Iniciamos un chat (sin historial para hacerlo simple y rápido, o puedes agregar history)
        chat_session = chat_model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- RUTA 3: GENERAR ARTE (Imagen o Video) ---
@app.route('/generate_art', methods=['POST']) # Cambié el nombre de la ruta para ser más general
def generate_art():
    try:
        data = request.json
        user_input = data.get("prompt", "")
        art_type = data.get("type", "image").lower() # 'image' o 'video'

        if not user_input:
            return jsonify({"result": "El lienzo necesita una idea."})

        # PASO 1: MEJORAR EL PROMPT (Usando Gemini Flash)
        prompt_instruction = f"""
        Actúa como un director de arte experto. 
        Transforma esta idea breve: "{user_input}" 
        en un PROMPT DETALLADO EN INGLÉS para una IA generativa de {art_type}.
        Asegúrate de que el prompt sea descriptivo, cinemático y muy detallado.
        Solo devuelve el prompt en inglés.
        """
        response_prompt = chat_model.generate_content(prompt_instruction)
        enhanced_prompt = response_prompt.text.strip()
        
        # PASO 2: GENERAR IMAGEN O VIDEO
        if art_type == "video":
            html_art = generar_video(enhanced_prompt)
        else: # Por defecto es imagen
            html_art = generar_imagen(enhanced_prompt)
        
        # PASO 3: CREAR UN TÍTULO POÉTICO
        response_caption = chat_model.generate_content(
            f"Escribe un título muy breve, abstracto y poético en español para esta {art_type}: {user_input}. No añadas ninguna explicación, solo el título."
        )
        caption = response_caption.text.strip()

        # PASO 4: EMPAQUETAR EL RESULTADO
        final_html = f"""
        <div class="artwork-wrapper">
            {html_art}
            <div class="caption">
                <strong>{caption}</strong><br>
                <span style="font-size:10px; color:#aaa;">Generado por Vista Engine ({art_type.capitalize()})</span>
            </div>
        </div>
        """
        return jsonify({"result": final_html})

    except Exception as e:
        print(f"❌ Error en el motor creativo de Vista: {e}")
        return jsonify({"result": f"<p style='color:red;'>Error en el motor creativo de Vista: {str(e)}</p>"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
