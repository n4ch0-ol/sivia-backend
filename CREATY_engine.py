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
# Permitimos CORS para que tu frontend (manos-unidas) pueda hablar con este backend
CORS(app)

# 2. CONFIGURACIÓN DE LA LLAVE MAESTRA
# En Render, debes crear la variable de entorno: CREATY_API_KEY
API_KEY = os.getenv("CREATY_API_KEY")

if not API_KEY:
    print("❌ ERROR CRÍTICO: No se encontró la variable CREATY_API_KEY.")
else:
    genai.configure(api_key=API_KEY)

# 3. DEFINICIÓN DE MODELOS
# Usamos Flash para pensar rápido (mejorar prompts)
TEXT_MODEL_NAME = "models/gemini-1.5-flash"
# Intentamos usar la joya de la corona: Imagen 3
IMAGEN_MODEL_NAME = "models/imagen-3.0-generate-001"

print(f"🎨 INICIANDO MOTOR CREATY...")

# --- FUNCIÓN: GENERADOR DE IMÁGENES HÍBRIDO ---
def generar_arte(prompt_optimizado):
    """
    Intenta generar con Google Imagen 3 (Calidad Cine).
    Si falla (por cuota o permiso), salta automáticamente a Flux (Pollinations).
    """
    try:
        print(f"🖌️ Intentando usar Google Imagen 3 con: {prompt_optimizado[:30]}...")
        
        # Conectamos con el modelo de imagen nativo
        imagen_model = genai.GenerativeModel(IMAGEN_MODEL_NAME)
        
        # Solicitud a Google
        result = imagen_model.generate_images(
            prompt=prompt_optimizado,
            number_of_images=1,
            aspect_ratio="16:9", 
            safety_filter_level="block_only_high"
        )
        
        # Procesamos la respuesta (Google devuelve bytes raw)
        image_bytes = result.images[0].image_bytes
        # Convertimos a base64 para que el navegador la entienda
        b64_string = base64.b64encode(image_bytes).decode('utf-8')
        
        # Retornamos HTML listo
        return f'<img src="data:image/jpeg;base64,{b64_string}" alt="Generado por Google Imagen 3" style="width:100%; border-radius:10px;">'

    except Exception as e:
        print(f"⚠️ Google Imagen 3 falló o no tiene permiso ({str(e)}).")
        print("🔄 Activando protocolo de respaldo (Flux)...")
        
        # FALLBACK: Usamos Pollinations si Google falla
        # Codificamos el prompt para URL
        import urllib.parse
        safe_prompt = urllib.parse.quote(prompt_optimizado)
        
        return f'<img src="https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologos=true&model=flux" alt="Generado por Flux" style="width:100%; border-radius:10px;">'

# --- RUTA PRINCIPAL (Comprobación de vida) ---
@app.route('/', methods=['GET'])
def home():
    return "CREATY ENGINE ONLINE /// Ready to Imagine."

# --- RUTA DE GENERACIÓN (El Cerebro) ---
@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        user_input = data.get("prompt", "")

        if not user_input:
            return jsonify({"result": "El lienzo necesita una idea."})

        # PASO 1: MEJORAR EL PROMPT (Usando Gemini Flash)
        # Convertimos la idea simple del usuario en una instrucción artística detallada
        text_model = genai.GenerativeModel(TEXT_MODEL_NAME)
        
        prompt_instruction = f"""
        Actúa como un director de arte experto. 
        Transforma esta idea breve: "{user_input}" 
        en un PROMPT DETALLADO EN INGLÉS para una IA generativa de imágenes.
        Estilo: Fotorealista, iluminación cinematográfica, 8k, muy detallado.
        Solo devuelve el prompt en inglés, nada más.
        """
        
        response_prompt = text_model.generate_content(prompt_instruction)
        enhanced_prompt = response_prompt.text.strip()
        
        # PASO 2: GENERAR LA IMAGEN (Google o Flux)
        html_imagen = generar_arte(enhanced_prompt)
        
        # PASO 3: CREAR UN TÍTULO POÉTICO
        response_caption = text_model.generate_content(
            f"Escribe un título muy breve, abstracto y poético en español para esta obra: {user_input}"
        )
        caption = response_caption.text.strip()

        # PASO 4: EMPAQUETAR EL RESULTADO
        # Devolvemos un bloque HTML completo que el frontend solo tiene que pegar
        final_html = f"""
        <div class="artwork-wrapper">
            {html_imagen}
            <div class="caption">
                <strong>{caption}</strong><br>
                <span style="font-size:10px; color:#aaa;">PROMPT: {enhanced_prompt[:40]}...</span>
            </div>
        </div>
        """

        return jsonify({"result": final_html})

    except Exception as e:
        print(f"❌ Error en el servidor: {e}")
        return jsonify({"result": f"<p>Error en el motor creativo: {str(e)}</p>"}), 500

if __name__ == '__main__':
    # Render asigna el puerto automáticamente en la variable PORT
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
