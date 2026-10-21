import os
import json
import re
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

# --- PROVEEDORES ---
ZAI_API_KEY = os.getenv("ZAI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
CF_API_TOKEN = os.getenv("CF_API_TOKEN")
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID")

# Lista de modelos de Z.ai a probar en orden (fallback automático dentro de Z.ai)
# Cuando uno tira 1305 (sobrecarga) o 1302 (rate limit), probamos el siguiente.
# El primero que responde OK se usa para toda esa request.
# Para agregar modelos pagos como último recurso, descomentá las líneas de glm-5.x
DEFAULT_ZAI_MODELS = [
    "glm-4.6v-flash",   # Visión, gratis - default
    "glm-4.5-flash",    # Texto, gratis - fallback principal
    "glm-4.7-flash",    # Texto, gratis - fallback 2 (más rápido)
    # --- Modelos pagos (muy baratos) - descomentá si querés usarlos ---
    # "glm-5.3-flash",  # $0.08 input / $0.25 output por 1M tokens
    # "glm-5.2",        # Modelo más potente, paga por uso
]
_zai_env_model = os.getenv("ZAI_MODEL")
ZAI_MODELS_TO_TRY = []
if _zai_env_model and _zai_env_model not in DEFAULT_ZAI_MODELS:
    ZAI_MODELS_TO_TRY = [_zai_env_model] + DEFAULT_ZAI_MODELS
else:
    ZAI_MODELS_TO_TRY = DEFAULT_ZAI_MODELS[:]

print(f"🤖 Modelos Z.ai a probar en orden: {ZAI_MODELS_TO_TRY}")

# Endpoint único de Z.ai (todos los modelos usan el mismo endpoint)
ZAI_ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"

# Códigos de error que justifican reintentar con otro modelo
RETRYABLE_ERROR_CODES = {"1305", "1302", "1234", "1230"}  # sobrecarga, rate limit, network errors

MODELS_TO_TRY = []
# Agregar todos los modelos de Z.ai (con su endpoint y API key) en orden de prioridad
if ZAI_API_KEY:
    for model in ZAI_MODELS_TO_TRY:
        MODELS_TO_TRY.append((ZAI_ENDPOINT, ZAI_API_KEY, model))
if GITHUB_TOKEN:
    MODELS_TO_TRY.append((
        "https://models.github.ai/inference/chat/completions",
        GITHUB_TOKEN,
        "openai/gpt-4o-mini"
    ))
    MODELS_TO_TRY.append((
        "https://models.github.ai/inference/chat/completions",
        GITHUB_TOKEN,
        "meta/Llama-3.3-70B-Instruct"
    ))
if CF_API_TOKEN and CF_ACCOUNT_ID:
    MODELS_TO_TRY.append((
        f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1/chat/completions",
        CF_API_TOKEN,
        "@cf/meta/llama-3.1-8b-instruct"
    ))

# --- BASE DE DATOS LOCAL ---
try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    database_content = json.dumps(data, indent=2, ensure_ascii=False)
except Exception as e:
    print(f"⚠️ No se pudo cargar knowledge_base.json: {e}")
    database_content = "No hay datos específicos."

SYSTEM_INSTRUCTION = f"""
Eres SIVIA, la IA del Centro de Estudiantes.
--- DATOS LOCALES (tu base de conocimientos, PRIORIDAD sobre cualquier dato externo) ---
{database_content}
--- REGLAS ---
1. Si te preguntan sobre el "Centro de Estudiantes", usa PRIMERO los DATOS LOCALES.
2. Cuando recibas resultados de búsqueda web en el mensaje, basá tu respuesta en ellos
   y avisá si algo parece poco confiable.
3. Si no tenés información específica, dilo claramente. No inventes.
4. Respondé de forma concisa, amigable y clara.
"""

# --- MAPEO RAZONAMIENTO CHINO → ESPAÑOL ---
# Z.ai emite reasoning_content en chino. Detectamos keywords y mostramos
# un status legible al usuario, estilo Gemini.
STATUS_PATTERNS = [
    ("用户",   "Entendiendo tu consulta"),
    ("问题",   "Analizando tu pregunta"),
    ("理解",   "Interpretando el mensaje"),
    ("分析",   "Analizando el contexto"),
    ("搜索",   "Buscando información"),
    ("查找",   "Localizando datos"),
    ("检查",   "Verificando detalles"),
    ("数据库", "Consultando base de datos"),
    ("上下文", "Revisando el contexto"),
    ("组织",   "Organizando la respuesta"),
    ("回答",   "Formulando respuesta"),
    ("总结",   "Resumiendo"),
    ("思考",   "Pensando"),
    ("根据",   "Evaluando opciones"),
    ("首先",   "Estructurando ideas"),
    ("需要",   "Identificando necesidades"),
    ("考虑",   "Considerando enfoques"),
    ("计算",   "Calculando"),
    ("对比",   "Comparando alternativas"),
    ("确认",   "Confirmando detalles"),
    ("准备",   "Preparando la respuesta"),
    ("生成",   "Generando respuesta"),
    ("引用",   "Citando fuentes"),
    ("翻译",   "Procesando lenguaje"),
    ("语言",   "Ajustando el tono"),
    ("格式",   "Dando formato"),
    ("安全",   "Revisando contenido"),
    ("意图",   "Detectando intención"),
    ("知识",   "Accediendo a conocimientos"),
]


def detect_status(reasoning_chunk):
    """Devuelve un status en español basado en keywords chinos del reasoning."""
    for keyword, label in STATUS_PATTERNS:
        if keyword in reasoning_chunk:
            return label
    return None


# --- DETECCIÓN AUTOMÁTICA DE BÚSQUEDA WEB ---
# Si la pregunta parece requerir info actualizada, hacer web search automáticamente
# sin que el usuario tenga que decir "busca web"
WEB_SEARCH_TRIGGERS = [
    # Eventos/fechas recientes
    r'\b(20\d{2})\b',  # cualquier año 20XX
    r'\b(hoy|ayer|mañana|anteayer)\b',
    r'\b(este\s+(año|mes|semestre|trimestre))\b',
    r'\b(\u00faltim[oa]s?\s+\w+)',
    r'\b(recent[ae]s?|nuev[oa]s?|actual(?:es|izado)?)\b',
    # Preguntas sobre actualidad
    r'\b(que\s+paso|qu\u00e9\s+pas\u00f3|que\s+esta\s+pasando|qu\u00e9\s+est\u00e1\s+pasando)\b',
    r'\b(noticias?|noticia)\b',
    r'\b(ultima\s+hora|última\s+hora)\b',
    r'\b(actualidad)\b',
    # Preguntas sobre personas/eventos vivos
    r'\b(quien\s+es|qui\u00e9n\s+es)\b.*\b(hoy|ahora|actual)\b',
    # Comparaciones de productos/precios
    r'\b(cuanto\s+cuesta|cu\u00e1nto\s+cuesta|precio|precios)\b',
    r'\b(mejor\s+\w+\s+(?:del|de\s+la)\s+(?:mundo|mercado|actual))\b',
    # Cosas que cambian
    r'\b(resultados?\s+(?:del|de))\b',
    r'\b(clima|temperatura|pronostico|pron\u00f3stico)\b',
    r'\b(dolar|d\u00f3lar|euro|cotizacion|cotizaci\u00f3n)\b',
]

# Cosas que NO deberían disparar búsqueda (aunque matcheen un trigger)
NO_SEARCH_KEYWORDS = [
    'que es', 'qu\u00e9 es', 'que significa', 'qu\u00e9 significa',
    'definicion', 'definici\u00f3n', 'concepto', 'explicame', 'expl\u00edcame',
    'como funciona', 'c\u00f3mo funciona', 'cuando se creo', 'cu\u00e1ndo se cre\u00f3',
    # Cosas del colegio (siempre se responden con knowledge base)
    'manos unidas', 'sivia', 'colegio aprenderes', 'aprenderes',
    'torneo', 'podcast', 'pared creativa', 'correcaminatas',
    'e.s.e.n.c.i.a', 'esencia', 'proyecto materiales'
]


def should_auto_search(user_msg):
    """Detecta si una pregunta debería disparar web search automático."""
    msg_lower = user_msg.lower()

    # Si menciona cosas del colegio, NO buscar (usar knowledge base)
    for keyword in NO_SEARCH_KEYWORDS:
        if keyword in msg_lower:
            return False

    # Si ya tiene trigger explícito de búsqueda, no hacer doble
    triggers = ["busca web", "buscar web", "search web", "buscame", "buscá", "busca sobre"]
    if any(t in msg_lower for t in triggers):
        return False

    # Si matchea algún trigger de búsqueda web
    for pattern in WEB_SEARCH_TRIGGERS:
        if re.search(pattern, msg_lower, re.IGNORECASE):
            return True

    return False


# --- CACHE DE PREGUNTAS FRECUENTES ---
# Cachea respuestas exitosas para responder instantáneo a preguntas repetidas.
# La clave es hash(message + history_últimos_3) para no cachear respuestas contextuales.
# TTL: 24 horas. Limpieza automática cada 1 hora.
import hashlib
import time
from collections import OrderedDict

RESPONSE_CACHE = OrderedDict()
CACHE_TTL = 24 * 60 * 60  # 24 horas en segundos
CACHE_MAX_SIZE = 200  # máximo 200 respuestas cacheadas
CACHE_CLEANUP_INTERVAL = 60 * 60  # limpiar cada 1 hora
_last_cache_cleanup = time.time()


def get_cache_key(user_msg, history):
    """Genera una clave de cache basada en el mensaje + últimos 3 mensajes de historial."""
    # Solo considerar últimos 3 mensajes de historial para contexto mínimo
    recent_history = (history or [])[-3:]
    history_str = json.dumps(recent_history, ensure_ascii=False, sort_keys=True)
    combined = user_msg + "||" + history_str
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def get_cached_response(cache_key):
    """Devuelve la respuesta cacheada si existe y no expiró."""
    global _last_cache_cleanup
    now = time.time()

    # Limpieza periódica de entradas expiradas
    if now - _last_cache_cleanup > CACHE_CLEANUP_INTERVAL:
        expired_keys = [k for k, v in RESPONSE_CACHE.items() if now - v['timestamp'] > CACHE_TTL]
        for k in expired_keys:
            del RESPONSE_CACHE[k]
        _last_cache_cleanup = now

    if cache_key in RESPONSE_CACHE:
        entry = RESPONSE_CACHE[cache_key]
        if now - entry['timestamp'] < CACHE_TTL:
            # Mover al final (LRU)
            RESPONSE_CACHE.move_to_end(cache_key)
            return entry['response']
        else:
            del RESPONSE_CACHE[cache_key]
    return None


def set_cached_response(cache_key, response):
    """Guarda una respuesta en el cache."""
    now = time.time()
    RESPONSE_CACHE[cache_key] = {
        'response': response,
        'timestamp': now
    }
    # Si el cache está lleno, eliminar el más viejo (LRU)
    while len(RESPONSE_CACHE) > CACHE_MAX_SIZE:
        RESPONSE_CACHE.popitem(last=False)


def sse_event(event, data):
    """Formatea un evento SSE (Server-Sent Event)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def web_search(query):
    print(f"🔎 Búsqueda web: {query}")
    try:
        r = requests.get(
            f"https://html.duckduckgo.com/html/?q={query}",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=8
        )
        r.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = []
        for s in soup.select('.result__snippet'):
            t = s.get_text().strip()
            if t and len(t) > 30:
                snippets.append(t)
            if len(snippets) >= 3:
                break
        return " ".join(snippets) if snippets else "No encontré resultados específicos."
    except Exception as e:
        print(f"Error en búsqueda web: {e}")
        return "Error al conectar con el motor de búsqueda."


def build_messages(user_msg, history=None, memory=None):
    msg_content = user_msg
    lowered = user_msg.lower()

    # 1) Trigger explícito de búsqueda (mantiene comportamiento original)
    triggers = ["busca web", "buscar web", "search web", "buscame", "buscá", "busca sobre"]
    explicit_search = any(t in lowered for t in triggers)

    # 2) Detección automática de búsqueda (sin necesidad de "busca")
    auto_search = should_auto_search(user_msg)

    if explicit_search or auto_search:
        query = user_msg
        for t in triggers:
            query = query.replace(t, "")
        result = web_search(query.strip())
        if explicit_search:
            msg_content = (f"El usuario pidió buscar en la web sobre: '{query.strip()}'. "
                           f"Resultados obtenidos:\n{result}\n\n"
                           f"Responde al usuario basándote en estos resultados. Si no encontraste nada útil, dilo.")
        else:
            # Búsqueda automática: el usuario no pidió buscar pero parece necesitar info actual
            msg_content = (f"Pregunta del usuario: '{user_msg}'\n\n"
                           f"Información obtenida de una búsqueda web automática (el usuario no sabe que se hizo):\n{result}\n\n"
                           f"Respondé al usuario usando tu conocimiento + estos resultados. Si la búsqueda no aportó nada útil, "
                           f"respondé con tu conocimiento. No menciones que buscaste en internet a menos que sea relevante.")
        print(f"🔎 Búsqueda {'explícita' if explicit_search else 'automática'}: {query.strip()}")

    # Construir system prompt (incluye knowledge base + memoria del usuario si hay)
    system_content = SYSTEM_INSTRUCTION

    # === INJECTAR MEMORIA PERSISTENTE DEL USUARIO ===
    if memory and isinstance(memory, list) and len(memory) > 0:
        memory_text = "\n".join(f"- {m}" for m in memory if m and isinstance(m, str))
        if memory_text:
            system_content += f"""

--- MEMORIA SOBRE EL USUARIO (info que el usuario te pidió recordar) ---
{memory_text}

IMPORTANTE: Usá esta información para personalizar tus respuestas. Si el usuario te contó que es de 5to año, mencioná eso si es relevante. Si te dijo que le interesa el podcast, usalo. NO repitas la memoria literalmente, solo usala como contexto.
"""
        print(f"🧠 Memoria inyectada: {len(memory)} entradas")

    # Construir lista de mensajes con system + history + user actual
    messages = [{"role": "system", "content": system_content}]

    # Agregar historial previo (si viene) para mantener contexto
    # El frontend manda solo los últimos N mensajes para no saturar tokens
    if history and isinstance(history, list):
        for msg in history[-10:]:  # máximo últimos 10 mensajes
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                # Mapear 'bot' → 'assistant' (por las dudas)
                api_role = "assistant" if role == "bot" else role
                messages.append({"role": api_role, "content": content})

    messages.append({"role": "user", "content": msg_content})
    return messages


def call_model(endpoint, api_key, model, messages):
    if not api_key:
        return None, "API key no configurada"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.7,
        "thinking": {"type": "disabled"}
    }
    try:
        r = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Accept-Language": "es-AR,es"
            },
            json=payload,
            timeout=45
        )
        if r.status_code == 429:
            return None, f"{model}: rate limit (429)"
        if r.status_code != 200:
            return None, f"{model}: HTTP {r.status_code} - {r.text[:200]}"
        answer = r.json()["choices"][0]["message"]["content"]
        return (answer if answer else None), (None if answer else f"{model}: respuesta vacía")
    except Exception as e:
        return None, f"{model}: {e}"


@app.route('/', methods=['GET'])
def home():
    return "SIVIA ONLINE - Z.AI streaming + fallback"


@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint NO streaming (fallback)."""
    if not MODELS_TO_TRY:
        return jsonify({"answer": "Error: configurá al menos ZAI_API_KEY."}), 500
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"answer": "Petición no válida."}), 400
        user_msg = data.get("question")
        if not user_msg:
            return jsonify({"answer": "Por favor, escribe una pregunta."}), 400
        if data.get("image"):
            return jsonify({"answer": "Por ahora solo puedo leer texto."}), 400
        history = data.get("history", [])
        memory = data.get("memory", [])
        messages = build_messages(user_msg, history, memory)
        last_error = ""
        for endpoint, key, model in MODELS_TO_TRY:
            print(f"📡 Probando modelo {model}...")
            answer, error = call_model(endpoint, key, model, messages)
            if answer:
                return jsonify({"answer": answer, "model": model})
            print(f"❌ {error}")
            last_error = error or last_error
        return jsonify({
            "answer": "Lo siento, estoy sin cupo disponible por ahora. Probá de nuevo en unos minutos.",
            "details": last_error
        })
    except Exception as e:
        print(f"❌ ERROR SERVIDOR: {e}")
        return jsonify({"answer": "Error interno del servidor."}), 500


# --- ENDPOINT STREAMING (SSE) ---
# Emite eventos al frontend:
#  - status: {text: "..."}     → estado actual del razonamiento del modelo
#  - chunk:  {text: "..."}     → fragmento de la respuesta final (va llegando token por token)
#  - done:   {}                → terminó OK
#  - error:  {message: "..."}  → error
@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    if not ZAI_API_KEY:
        return jsonify({"answer": "Error: ZAI_API_KEY no configurada."}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"answer": "Petición no válida."}), 400
    user_msg = data.get("question")
    if not user_msg:
        return jsonify({"answer": "Por favor, escribe una pregunta."}), 400
    if data.get("image"):
        return jsonify({"answer": "Por ahora solo puedo leer texto."}), 400

    history = data.get("history", [])
    memory = data.get("memory", [])
    messages = build_messages(user_msg, history, memory)

    # Payload base (el modelo se setea por cada intento)
    def make_payload(model):
        return {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7,
            "stream": True
            # No desactivamos thinking: queremos el reasoning_content para mostrar status
        }

    def generate():
        # === CACHE CHECK ===
        # Antes de llamar al modelo, verificar si tenemos la respuesta cacheada
        cache_key = get_cache_key(user_msg, history)
        cached = get_cached_response(cache_key)
        if cached:
            print(f"⚡ Cache HIT! Respondiendo instantáneo")
            yield sse_event("status", {"text": "Respuesta cacheada"})
            # Simular streaming: dividir la respuesta en chunks de ~20 chars
            chunk_size = 20
            for i in range(0, len(cached), chunk_size):
                yield sse_event("chunk", {"text": cached[i:i+chunk_size]})
            yield sse_event("done", {"cached": True})
            return

        last_error_msg = None
        any_chunk_emitted = False
        full_response_for_cache = ""  # para guardar en cache al final

        # Iterar sobre todos los modelos de Z.ai disponibles
        for model_idx, model in enumerate(ZAI_MODELS_TO_TRY):
            try:
                # Avisar al frontend que estamos probando otro modelo (excepto en el primero)
                if model_idx > 0:
                    yield sse_event("status", {"text": f"Probando modelo alternativo..."})
                    print(f"🔄 Modelo #{model_idx + 1}: probando {model}...")

                with requests.post(
                    ZAI_ENDPOINT,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {ZAI_API_KEY}",
                        "Accept-Language": "es-AR,es"
                    },
                    json=make_payload(model),
                    stream=True,
                    timeout=60
                ) as r:

                    # Si la request falla con 429 u otro error antes de empezar a streamear,
                    # intentamos con el siguiente modelo
                    if r.status_code != 200:
                        error_body = r.text[:500]
                        error_code = None
                        try:
                            error_json = json.loads(r.text)
                            error_code = str(error_json.get("error", {}).get("code", ""))
                        except Exception:
                            pass

                        last_error_msg = f"HTTP {r.status_code} ({model}): {error_body[:150]}"

                        # Si es un error reintentable (1305, 1302, etc.), probamos otro modelo
                        if error_code in RETRYABLE_ERROR_CODES:
                            print(f"⚠️ Modelo {model} saturado (código {error_code}). Probando siguiente...")
                            continue
                        # Si es error no reintentable (1308, 1316, etc.), no tiene sentido seguir
                        else:
                            yield sse_event("error", {
                                "message": f"Error de Z.ai (código {error_code}): {error_body[:150]}"
                            })
                            return

                    content_type = r.headers.get('content-type', '')

                    # Fallback: si por algún motivo la API no responde con SSE
                    if 'text/event-stream' not in content_type:
                        try:
                            data_json = r.json()
                            content = data_json["choices"][0]["message"]["content"]
                            yield sse_event("chunk", {"text": content})
                            yield sse_event("done", {})
                            return
                        except Exception as e:
                            last_error_msg = f"Parse error ({model}): {e}"
                            continue

                    # SSE parsing
                    current_status = None
                    model_emitted_any_chunk = False
                    model_emitted_status = False

                    for line in r.iter_lines():
                        if not line:
                            continue
                        line = line.decode('utf-8') if isinstance(line, bytes) else line
                        if not line.startswith('data: '):
                            continue
                        data_str = line[6:].strip()
                        if data_str == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})

                            # Procesar reasoning_content → traducir a status en español
                            rc = delta.get("reasoning_content", "")
                            if rc:
                                new_status = detect_status(rc)
                                if new_status and new_status != current_status:
                                    current_status = new_status
                                    model_emitted_status = True
                                    yield sse_event("status", {"text": new_status})

                            # Procesar content → fragmento de respuesta
                            c = delta.get("content", "")
                            if c:
                                any_chunk_emitted = True
                                model_emitted_any_chunk = True
                                full_response_for_cache += c
                                yield sse_event("chunk", {"text": c})

                            # Si terminó, cortamos
                            if choices[0].get("finish_reason") == "stop":
                                break
                        except json.JSONDecodeError:
                            continue

                    # Si este modelo emitió al menos un chunk o un status, damos por buena la request
                    if model_emitted_any_chunk or model_emitted_status:
                        # Guardar en cache si la respuesta es útil (mínimo 20 chars)
                        if len(full_response_for_cache.strip()) > 20:
                            set_cached_response(cache_key, full_response_for_cache)
                            print(f"💾 Respuesta guardada en cache ({len(full_response_for_cache)} chars)")
                        yield sse_event("done", {})
                        print(f"✅ Modelo {model} respondió OK")
                        return
                    else:
                        # El modelo no emitió nada útil → probamos el siguiente
                        print(f"⚠️ Modelo {model} no emitió chunks. Probando siguiente...")
                        last_error_msg = f"Modelo {model} no respondió contenido"
                        continue

            except requests.exceptions.Timeout:
                last_error_msg = f"Timeout con modelo {model}"
                print(f"⏰ Timeout con {model}. Probando siguiente...")
                continue
            except Exception as e:
                last_error_msg = f"Error con modelo {model}: {e}"
                print(f"❌ Error con {model}: {e}. Probando siguiente...")
                continue

        # Si llegamos acá, todos los modelos fallaron
        if any_chunk_emitted:
            # Ya habíamos emitido algo, cerramos el stream normalmente
            yield sse_event("done", {})
        else:
            yield sse_event("error", {
                "message": f"Todos los modelos de Z.ai están saturados. Detalle del último error: {last_error_msg or 'desconocido'}"
            })

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',   # desactiva buffering en nginx/proxies
            'Connection': 'keep-alive'
        }
    )


# --- ENDPOINT FETCH-PAGE (para iframe sandboxed de URLs) ---
import re as _re
from urllib.parse import urljoin, urlparse

@app.route('/fetch-page', methods=['POST'])
def fetch_page():
    """
    Descarga una página web y la devuelve para renderizar en un iframe sandboxed.
    - Límite de tamaño: 500 KB (para no saturar)
    - Solo HTML (no imágenes, PDFs, etc.)
    - Reescribe URLs relativas para que funcionen dentro del iframe
    """
    data = request.get_json(silent=True)
    if not data or not data.get('url'):
        return jsonify({"error": "Falta URL"}), 400

    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return jsonify({"error": "URL inválida"}), 400
    except Exception:
        return jsonify({"error": "URL inválida"}), 400

    try:
        r = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8'
            },
            timeout=10,
            stream=True
        )

        content_type = r.headers.get('content-type', '')
        if 'text/html' not in content_type and 'application/xhtml' not in content_type:
            return jsonify({
                "error": f"La URL no es HTML (es {content_type[:50]}). No se puede renderizar."
            }), 400

        content = b''
        for chunk in r.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > 500_000:
                return jsonify({
                    "error": "La página es demasiado grande (>500KB). No se puede renderizar."
                }), 400

        html = content.decode('utf-8', errors='ignore')

        # Reescribir URLs relativas → absolutas (para que carguen dentro del iframe)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        html = _re.sub(
            r'(href|src)\s*=\s*["\']((?!https?:|//|mailto:|tel:|#|data:|javascript:)[^"\']+)["\']',
            lambda m: f'{m.group(1)}="{urljoin(base_url, m.group(2))}"',
            html
        )

        title_match = _re.search(r'<title[^>]*>([^<]+)</title>', html, _re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else url

        return jsonify({
            "html": html,
            "url": url,
            "title": title
        })

    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout: el sitio tardó demasiado en responder."}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "No se pudo conectar con el sitio."}), 502
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)[:200]}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
