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
import re

modelo = "grok-4-1-fast-reasoning"

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

        # === 1. Gera texto com Grok (igual antes) ===
        chat = client_xai.chat.create(
            model=modelo,
            messages=[
                system(FULL_SYSTEM_PROMPT),
                user(question)
            ],
        )
        response = chat.sample()
        raw_content = response.content.strip()

        # === 2. Extrai JSON da resposta (seu código já perfeito) ===
        match = re.search(r'(\{.*\})', raw_content, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = raw_content

        try:
            answer_json = json.loads(json_str)
            answer_text = answer_json.get('resposta', raw_content)
            ctas = answer_json.get('ctas', [])
            cta_0 = ctas[0] if len(ctas) > 0 else None
            cta_1 = ctas[1] if len(ctas) > 1 else None
        except json.JSONDecodeError:
            answer_text = raw_content
            cta_0, cta_1 = None, None


        # === 3. Gera imagem com Flux (VERSÃO OFICIAL E SEM ERRO – DE ACORDO COM A DOC xAI) ===
        image_url = None
        should_generate_image = any(palavra in question.lower() for palavra in [
            "foto", "imagem", "mostre", "mostra", "show", "photo", "picture", "visual", 
            "projeto", "dashboard", "gráfico", "graph", "agrotech", "drone", "iot", "fazenda",
            "farm", "campo", "máquina", "tractor", "plantação", "ia", "ai", "llm", "machine learning",
            "python", "dados", "startup", "leadership", "team", "projeto"  # Cobrindo mais perguntas
        ])

        if False and should_generate_image:
            try:
                # Prompt direto em inglês (ótimo pro Flux)
                flux_prompt = f"Professional, modern, photorealistic image related to the query: '{question}'. Theme: Data Science, Agrotech IoT, drones over soy farms, sensors in agriculture, Python code dashboards, AI agents, team leadership in startups, or Brazilian precision farming. Cinematic lighting, high quality, 8k, no text, no close-up people, neutral background for website use."
                
                # GERA A IMAGEM (EXATO DA DOC: client.image.sample() com image_format="url")
                img_response = client_xai.image.sample(
                    model="grok-2-image",  # Modelo oficial e estável pra imagens
                    prompt=flux_prompt,
                    image_format="url"  # Retorna URL pública (válida ~1h)
                )
                image_url = img_response.url  # ← DIRETO ASSIM, SEM data[]
                
                logger.info(f"Imagem gerada com sucesso para '{question}': {image_url}")
                
            except Exception as e:
                logger.warning(f"Erro ao gerar imagem para '{question}': {e}")
                image_url = None


        # === 4. Log e retorno (igual antes, + imagem) ===
        log_payload = {
            "event_type": "chat_interaction",
            "user_question": question,
            "ai_response": answer_text,
            "cta_suggested": [cta_0, cta_1],
            "image_generated": bool(image_url),
            "status": "success",
            "model": modelo
        }
        logger.info(json.dumps(log_payload, ensure_ascii=False))

        return JSONResponse({
            "response": answer_text,
            "call_action0": cta_0,
            "call_action1": cta_1,
            "background_image": image_url  # ← Envia a URL pro frontend
        })

    except Exception as e:
        # Seu error handling...
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
    return {"status": "ok", "model": modelo}

# Startup message
@app.on_event("startup")
async def startup_event():
    print("\nEleandro Gaioski - Currículo com IA")
    print("Acesse: http://localhost:8000\n")
    
#para debug:
#uvicorn main:app --host 0.0.0.0 --port 8000 --reload