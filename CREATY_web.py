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
            <input id="prompt" type="text" placeholder="Ej: Un capibara astronauta" style="padding: 10px; width: 300px;">
            <button onclick="generate()" style="padding: 10px 20px; cursor: pointer;">GENERAR</button>
            <br><br>
            <div id="status"></div>
            <img id="result" style="max-width: 500px; margin-top: 20px; border-radius: 10px; box-shadow: 0 0 20px rgba(255,255,255,0.1);">
            
            <script>
                async function generate() {
                    const prompt = document.getElementById('prompt').value;
                    const status = document.getElementById('status');
                    const img = document.getElementById('result');
                    
                    if(!prompt) return alert("Escribe algo!");
                    
                    status.innerText = "⏳ Generando... (Esto tarda unos segundos)";
                    img.style.display = 'none';
                    
                    try {
                        const response = await fetch('/generate', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ prompt: prompt })
                        });
                        
                        const data = await response.json();
                        
                        if(data.image) {
                            img.src = "data:image/png;base64," + data.image;
                            img.style.display = 'block';
                            status.innerText = "✅ ¡Listo!";
                        } else {
                            status.innerText = "❌ Error: " + (data.error || "Desconocido");
                        }
                    } catch (e) {
                        status.innerText = "❌ Error de conexión";
                    }
                }
            </script>
        </body>
    </html>
    """

@app.route('/generate', methods=['POST'])
def generate():
    if not GOOGLE_API_KEY:
        return jsonify({"error": "Falta API KEY en .env"}), 500

    try:
        data = request.json
        prompt = data.get("prompt")
        
        # Opciones avanzadas (puedes cambiarlas)
        # aspectRatio: "1:1", "16:9", "4:3", "3:4", "9:16"
        aspect_ratio = data.get("aspectRatio", "1:1") 

        print(f"🖌️  Pintando: '{prompt}'...")

        # Estructura EXACTA que pide Google para Imagen
        payload = {
            "instances": [
                {
                    "prompt": prompt
                }
            ],
            "parameters": {
                "sampleCount": 1, # Solo 1 imagen por ahora
                "aspectRatio": aspect_ratio
            }
        }

        # Enviamos la petición directa
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=60 # Damos hasta 60 segundos
        )

        if response.status_code != 200:
            print(f"❌ Error Google: {response.text}")
            return jsonify({"error": f"Google rechazó el pedido ({response.status_code})."}), response.status_code

        # Parseamos la respuesta
        result = response.json()
        
        # La imagen viene en base64 dentro de 'predictions'
        try:
            image_b64 = result['predictions'][0]['bytesBase64Encoded']
            return jsonify({"image": image_b64})
        except (KeyError, IndexError):
            return jsonify({"error": "Google no devolvió ninguna imagen (Posible filtro de seguridad)."}), 500

    except Exception as e:
        print(f"❌ Error interno: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
