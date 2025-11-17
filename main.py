# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from xai_sdk import Client
from xai_sdk.chat import system, user  # <<<< IMPORTANTE: helpers para messages
from dotenv import load_dotenv
import json
import os
import logging

# ===================== CONFIGURAÇÃO =====================
load_dotenv()

app = FastAPI(
    title="Eleandro Gaioski - Currículo com IA",
    description="Assistente virtual que responde sobre minha carreira",
    version="1.0.0"
)

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

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
client = Client(api_key=os.getenv("XAI_API_KEY"))

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
        data = await request.json()
        question = data.get("message", "").strip()

        if not question:
            return JSONResponse({"response": "Oi! Pode mandar sua pergunta sobre minha carreira."})

        # <<<< AQUI ESTÁ A CORREÇÃO: formato correto com helpers system/user
        chat = client.chat.create(
            model="grok-4-fast-reasoning",
            messages=[
                system(FULL_SYSTEM_PROMPT),
                user(question)
            ]
        )

        # Gera resposta
        response = chat.sample()
        answer = response.content.strip()

        logger.info(f"Pergunta: {question[:60]}... | Resposta gerada com sucesso.")
        return JSONResponse({"response": answer})

    except Exception as e:
        logger.error(f"Erro no /chat: {str(e)}")
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
    
    
    



