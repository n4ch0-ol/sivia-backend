import os
import requests
import base64
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import io

# 1. CONFIGURACIÓN
load_dotenv()
app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 2. MODELO DE IMAGEN (Imagen 3)
# Este es el modelo estándar para generar imágenes en la API v1beta
MODEL_NAME = "imagen-3.0-generate-001"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:predict?key={GOOGLE_API_KEY}"

print(f"🎨 CREATY ENGINE ONLINE - Usando: {MODEL_NAME}")

@app.route('/', methods=['GET'])
def home():
    # Una mini interfaz integrada para que pruebes si funciona rápido
    return """
    <html>
        <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #1a1a1a; color: white;">
            <h1>🎨 CREATY ENGINE</h1>
            <p>Escribe algo y crearé una imagen.</p>

            <div style="background: #2a2a2a; padding: 20px; border-radius: 15px; display: inline-block; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <input id="prompt" type="text" placeholder="Ej: Un capibara astronauta en Marte"
                       style="padding: 12px; width: 350px; border-radius: 8px; border: none; outline: none; font-size: 16px;">

                <select id="aspectRatio" style="padding: 11px; border-radius: 8px; border: none; cursor: pointer; font-size: 16px; background: #444; color: white; margin-left: 10px;">
                    <option value="1:1">1:1 (Cuadrado)</option>
                    <option value="16:9">16:9 (Horizontal)</option>
                    <option value="9:16">9:16 (Vertical)</option>
                    <option value="4:3">4:3 (Clásico)</option>
                    <option value="3:4">3:4 (Retrato)</option>
                </select>

                <button onclick="generate()" style="padding: 12px 25px; border-radius: 8px; border: none; background: #3b82f6; color: white; font-weight: bold; cursor: pointer; margin-left: 10px; transition: 0.3s;">
                    GENERAR
                </button>
            </div>

            <br><br>
            <div id="status" style="font-weight: bold; min-height: 24px;"></div>
            <img id="result" style="max-width: 90%; max-height: 600px; margin-top: 20px; border-radius: 10px; box-shadow: 0 0 30px rgba(255,255,255,0.1); display: none;">
            
            <script>
                async function generate() {
                    const prompt = document.getElementById('prompt').value;
                    const aspectRatio = document.getElementById('aspectRatio').value;
                    const status = document.getElementById('status');
                    const img = document.getElementById('result');
                    
                    if(!prompt) return alert("¡Escribe una descripción primero!");
                    
                    status.innerHTML = "<span style='color: #60a5fa;'>⏳ Generando... (Esto tarda unos segundos)</span>";
                    img.style.display = 'none';
                    
                    try {
                        const response = await fetch('/generate', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ prompt: prompt, aspectRatio: aspectRatio })
                        });
                        
                        const data = await response.json();
                        
                        if(data.image) {
                            img.src = "data:image/png;base64," + data.image;
                            img.style.display = 'inline-block';
                            status.innerHTML = "<span style='color: #4ade80;'>✅ ¡Listo!</span>";
                        } else {
                            status.innerHTML = "<span style='color: #f87171;'>❌ Error: " + (data.error || "Desconocido") + "</span>";
                        }
                    } catch (e) {
                        status.innerHTML = "<span style='color: #f87171;'>❌ Error de conexión</span>";
                    }
                }
            </script>
        </body>
    </html>
    """

@app.route('/generate', methods=['POST'])
def generate():
    if not GOOGLE_API_KEY:
        return jsonify({"error": "Falta API KEY en el entorno o archivo .env"}), 500

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No se recibió un JSON válido."}), 400

        prompt = data.get("prompt")
        if not prompt:
            return jsonify({"error": "El prompt es obligatorio."}), 400
        
        # Opciones avanzadas
        # aspectRatio: "1:1", "16:9", "4:3", "3:4", "9:16"
        aspect_ratio = data.get("aspectRatio", "1:1") 

        print(f"🖌️  Pintando: '{prompt}' (Ratio: {aspect_ratio})...")

        # Estructura optimizada para Google Imagen 3
        payload = {
            "instances": [
                {
                    "prompt": prompt
                }
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio,
                "safetySetting": "BLOCK_ONLY_HIGH",
                "personGeneration": "ALLOW_ADULT"
            }
        }

        # Enviamos la petición directa
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=60
        )

        # Parseamos la respuesta
        result = response.json()

        if response.status_code != 200:
            error_msg = result.get('error', {}).get('message', response.text)
            print(f"❌ Error Google ({response.status_code}): {error_msg}")
            return jsonify({"error": f"Google API Error: {error_msg}"}), response.status_code

        # La imagen viene en base64 dentro de 'predictions'
        if 'predictions' in result and len(result['predictions']) > 0:
            prediction = result['predictions'][0]
            if 'bytesBase64Encoded' in prediction:
                return jsonify({"image": prediction['bytesBase64Encoded']})
            elif 'base64' in prediction:
                return jsonify({"image": prediction['base64']})

        # Si no hay predicciones, puede ser por filtros de seguridad
        print(f"⚠️ Respuesta sin imagen: {result}")
        return jsonify({"error": "Google no generó la imagen. Puede que el prompt haya sido filtrado por seguridad."}), 500

    except Exception as e:
        print(f"❌ Error interno: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
