# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from xai_sdk import Client
from xai_sdk.chat import system, user 
from dotenv import load_dotenv
import json
import os
import sys
import logging

# ===================== LOGGING GOOGLE CLOUD =====================
# Tenta configurar o logging do Google. Se falhar (rodando local), usa o padrão.
try:
    import google.cloud.logging
    from google.cloud.logging.handlers import CloudLoggingHandler
    
    # Instancia o cliente
    client = google.cloud.logging.Client()
    # Conecta o logger do Python ao Google Cloud Logging
    client.setup_logging()
    logging.info("Google Cloud Logging ativado com sucesso.")
except ImportError:
    print("Biblioteca google-cloud-logging não encontrada. Usando log padrão.")
except Exception as e:
    print(f"Rodando localmente ou sem credenciais GCP: {e}")

# Configuração padrão do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("curr-ia-logger") # Nome do logger para facilitar busca

# ===================== CONFIGURAÇÃO =====================
load_dotenv()

app = FastAPI(
    title="Eleandro Gaioski - Currículo com IA",
    description="Assistente virtual que responde sobre minha carreira",
    version="1.0.0"
)

# Força UTF-8 para encoding
sys.stdout.reconfigure(encoding='utf-8')

# Permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pastas estáticas
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# ===================== CARGA DE DADOS =====================
try:
    with open("data/curriculum.json", "r", encoding="utf-8") as f:
        curriculum = json.load(f)
    curriculum_text = json.dumps(curriculum, indent=2, ensure_ascii=False)

    with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    FULL_SYSTEM_PROMPT = f"{system_prompt}\n\nCurrículo completo (em JSON):\n{curriculum_text}"

except FileNotFoundError as e:
    logger.error(f"Arquivo não encontrado: {e}")
    raise RuntimeError(f"Arquivo obrigatório ausente: {e}")

# Cliente xAI
client_xai = Client(api_key=os.getenv("XAI_API_KEY"))

if not os.getenv("XAI_API_KEY"):
    logger.error("XAI_API_KEY não encontrada no .env")
    raise RuntimeError("Configure a variável XAI_API_KEY no arquivo .env")

# ===================== ROTAS =====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat")
async def chat_endpoint(request: Request):
    try:
        data_req = await request.json()
        question = data_req.get("message", "").strip()

        if not question:
            return JSONResponse({"response": "Oi! Pode mandar sua pergunta sobre minha carreira."})

        # Chamada à API xAI
        chat = client_xai.chat.create(
            model="grok-4-fast-reasoning",
            messages=[
                system(FULL_SYSTEM_PROMPT),
                user(question)
            ],
        )

        # Processa resposta
        response = chat.sample()
        
        # Tenta fazer o parse do JSON retornado pela IA
        try:
            answer_json = json.loads(response.content.strip())
            answer_text = answer_json.get('resposta', "Sem resposta.")
            cta_0 = answer_json.get('ctas', [None, None])[0]
            cta_1 = answer_json.get('ctas', [None, None])[1]
        except json.JSONDecodeError:
            # Fallback caso a IA não devolva JSON válido
            answer_text = response.content.strip()
            cta_0, cta_1 = None, None
            logger.warning(f"Falha ao decodificar JSON da IA. Resposta crua: {answer_text}")

        # -------------------------------------------------------
        # 🌟 AQUI ESTÁ O SEGREDO DO LOG ESTRUTURADO 🌟
        # -------------------------------------------------------
        log_payload = {
            "event_type": "chat_interaction",
            "user_question": question,
            "ai_response": answer_text,
            "cta_suggested": [cta_0, cta_1],
            "status": "success",
            "model": "grok-4-fast-reasoning"
        }
        
        # Ao enviar um JSON dump, o Google Cloud Logging faz o parse automático
        # e coloca isso dentro de jsonPayload no console.
        logger.info(json.dumps(log_payload, ensure_ascii=False))

        return JSONResponse({"response": answer_text, "call_action0": cta_0, "call_action1": cta_1})

    except Exception as e:
        # Log de erro também estruturado
        error_payload = {
            "event_type": "chat_error",
            "error_message": str(e),
            "user_question": question if 'question' in locals() else "unknown"
        }
        logger.error(json.dumps(error_payload, ensure_ascii=False))
        
        return JSONResponse(
            {"response": "Desculpe, tive um problema técnico no momento. Tente novamente em alguns segundos."},
            status_code=500
        )

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "model": "grok-4-fast-reasoning"}

# Startup message
@app.on_event("startup")
async def startup_event():
    print("\nEleandro Gaioski - Currículo com IA")
    print("Acesse: http://localhost:8000\n")