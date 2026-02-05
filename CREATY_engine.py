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
CREATY_API_KEY = os.getenv("CREATY_API_KEY")

if not CREATY_API_KEY:
    print("❌ ERROR CRÍTICO: No se encontró la variable CREATY_API_KEY.")
else:
    genai.configure(api_key=CREATY_API_KEY)

# --- FUNCIÓN INTELIGENTE: BUSCADOR DE MODELOS ---
def buscar_modelo_texto_disponible():
    """
    Pregunta a Google qué modelos tiene la cuenta y elige el mejor (Flash > Pro 1.5 > Pro).
    """
    print("🔍 VISTA está escaneando modelos disponibles...")
    try:
        modelos = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos.append(m.name)
        
        # 1. Prioridad: Flash (Rápido)
        for m in modelos:
            if 'gemini-1.5-flash' in m:
                print(f"✅ Modelo seleccionado: {m}")
                return m
        
        # 2. Prioridad: Pro 1.5 (Potente)
        for m in modelos:
            if 'gemini-1.5-pro' in m:
                print(f"✅ Modelo seleccionado: {m}")
                return m
        
        # 3. Fallback: Gemini Pro Clásico
        for m in modelos:
            if 'gemini-pro' in m:
                print(f"✅ Modelo seleccionado: {m}")
                return m

        # Si no encuentra nada conocido, usa el primero de la lista
        if modelos:
            print(f"⚠️ Usando primer modelo disponible: {modelos[0]}")
            return modelos[0]
            
    except Exception as e:
        print(f"⚠️ Error listando modelos ({e}). Usando fallback manual.")
    
    return "gemini-1.5-flash" # Último recurso si falla el listado

# 3. DEFINICIÓN DE MODELOS
# Usamos la función para el texto:
CREATY_TEXT_MODEL_NAME = buscar_modelo_texto_disponible()

# Para Imagen y Video mantenemos los específicos (son experimentales y no siempre aparecen en listas estándar)
CREATY_IMAGE_MODEL_NAME = "models/imagen-3.0-generate-001"
CREATY_VIDEO_MODEL_NAME = "models/veo-001" 

# --- CONFIGURACIÓN DE LA PERSONALIDAD "VISTA" ---
sistema_instrucciones_vista = """
Tu nombre es Vista. 
Eres una asistente creativa, inteligente y amable del motor CREATY.
Tu principal función es ayudar a los usuarios a generar imágenes y videos.
Cuando generas imágenes o videos, indicas que estás usando el "motor de Vista".
Tus respuestas son concisas, útiles y siempre te mantienes en personaje como "Vista".
Si el usuario pide una imagen o video, enfócate en pedir detalles para el prompt.
"""

# Instanciamos el modelo de chat con la instrucción de sistema
try:
    chat_model = genai.GenerativeModel(
        model_name=CREATY_TEXT_MODEL_NAME,
        system_instruction=sistema_instrucciones_vista
    )
    print(f"🎨 MOTOR VISTA INICIADO (Modelo base: {CREATY_TEXT_MODEL_NAME})")
except Exception as e:
    print(f"❌ Error fatal iniciando chat_model: {e}")

# --- FUNCIÓN: GENERADOR DE IMÁGENES HÍBRIDO ---
def generar_imagen(prompt_optimizado):
    try:
        print(f"🖌️ Intentando usar Google Imagen 3 con: {prompt_optimizado[:50]}...")
        # Nota: Imagen 3 requiere estar en la whitelist de Trusted Testers en algunos casos
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
        print(f"⚠️ Google Imagen 3 falló ({str(e)}). Activando Fallback Flux...")
        import urllib.parse
        safe_prompt = urllib.parse.quote(prompt_optimizado)
        # Fallback a Pollinations (Flux) que es gratuito y no requiere API Key
        return f'<img src="https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologos=true&model=flux" alt="Imagen generada por Vista (Flux)" style="width:100%; border-radius:10px;">'

# --- FUNCIÓN: GENERADOR DE VIDEO (con Veo) ---
def generar_video(prompt_optimizado):
    try:
        print(f"🎥 Intentando usar Google Veo con: {prompt_optimizado[:50]}...")
        video_model = genai.GenerativeModel(CREATY_VIDEO_MODEL_NAME)
        
        # OJO: Veo es muy restrictivo y lento en alpha.
        result = video_model.generate_videos(
            prompt=prompt_optimizado,
            number_of_videos=1,
            video_length_seconds=4, # Máximo usual
            aspect_ratio="16:9", 
            safety_filter_level="block_only_high"
        )
        
        # Veo tarda en procesar. Aquí asumimos que la API devuelve la URI rápido,
        # pero a veces requiere polling (esperar).
        video_uri = result.videos[0].uri 
        
        return f'<video controls loop autoplay src="{video_uri}" alt="Video generado por Vista (Veo)" style="width:100%; border-radius:10px;"></video>'

    except Exception as e:
        print(f"❌ Error Veo: {str(e)}")
        return f'<p style="color:#f87171; font-size:0.9em;">⚠️ El motor de video (Veo) está ocupado o no disponible en este momento. Error: {str(e)}</p>'


# --- RUTA 1: HOME ---
@app.route('/', methods=['GET'])
def home():
    return f"CREATY ENGINE ONLINE /// Soy Vista. Modelo Text: {CREATY_TEXT_MODEL_NAME}"

# --- RUTA 2: CHAT (El Cerebro de Vista) ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Iniciamos sesión sin historial para agilidad
        chat_session = chat_model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        
        return jsonify({"response": response.text})
    except Exception as e:
        print(f"Error en chat: {e}")
        return jsonify({"error": str(e)}), 500

# --- RUTA 3: GENERAR ARTE (Imagen o Video) ---
@app.route('/generate_art', methods=['POST']) 
def generate_art():
    try:
        data = request.json
        user_input = data.get("prompt", "")
        art_type = data.get("type", "image").lower() # 'image' o 'video'

        if not user_input:
            return jsonify({"result": "El lienzo necesita una idea."})

        # PASO 1: MEJORAR EL PROMPT
        prompt_instruction = f"""
        Actúa como un director de arte experto. 
        Transforma esta idea breve: "{user_input}" 
        en un PROMPT DETALLADO EN INGLÉS para una IA generativa de {art_type}.
        Solo devuelve el prompt en inglés.
        """
        response_prompt = chat_model.generate_content(prompt_instruction)
        enhanced_prompt = response_prompt.text.strip()
        
        # PASO 2: GENERAR IMAGEN O VIDEO
        if art_type == "video":
            html_art = generar_video(enhanced_prompt)
        else: 
            html_art = generar_imagen(enhanced_prompt)
        
        # PASO 3: TÍTULO
        response_caption = chat_model.generate_content(
            f"Escribe un título muy breve, abstracto y poético en español para: {user_input}. Solo el título."
        )
        caption = response_caption.text.strip()

        # PASO 4: RESULTADO HTML
        final_html = f"""
        <div class="artwork-wrapper">
            {html_art}
            <div class="caption" style="margin-top:10px;">
                <strong>{caption}</strong><br>
                <span style="font-size:10px; color:#aaa;">Generado por Vista Engine ({art_type.capitalize()})</span>
            </div>
        </div>
        """
        return jsonify({"result": final_html})

    except Exception as e:
        print(f"❌ Error general en generate_art: {e}")
        return jsonify({"result": f"<p style='color:red;'>Error creando arte: {str(e)}</p>"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
