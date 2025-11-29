
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
import base64  # Necessário para converter a imagem para o Frontend

# Imports do Google GenAI
from google import genai
from google.genai import types

# === DEFINIÇÃO DOS MODELOS ===
modelo_chat = "grok-4-fast-reasoning"
modelo_imagem = "imagen-4.0-fast-generate-001" 

# ===================== LOGGING GOOGLE CLOUD =====================
try:
    import google.cloud.logging
    from google.cloud.logging.handlers import CloudLoggingHandler
    
    # Instancia o cliente de LOGS
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging()
    logging.info("Google Cloud Logging ativado com sucesso.")
except ImportError:
    print("Biblioteca google-cloud-logging não encontrada. Usando log padrão.")
except Exception as e:
    print(f"Rodando localmente ou sem credenciais GCP: {e}")

# Configuração padrão do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("curr-ia-logger")

# ===================== CONFIGURAÇÃO =====================
load_dotenv()

app = FastAPI(
    title="Eleandro Gaioski - Currículo com IA",
    description="Assistente virtual que responde sobre minha carreira",
    version="1.0.0"
)

# Força UTF-8 para encoding no terminal
sys.stdout.reconfigure(encoding='utf-8')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# === INICIALIZAÇÃO DOS CLIENTES DE IA ===

# 1. Cliente xAI (Para Texto e Refinamento de Prompt)
if not os.getenv("XAI_API_KEY"):
    raise RuntimeError("Configure a variável XAI_API_KEY no arquivo .env")
client_xai = Client(api_key=os.getenv("XAI_API_KEY"))

# 2. Cliente Google GenAI (Para Geração de Imagem)
if not os.getenv("GEMINI_API_KEY"):
    logger.warning("GEMINI_API_KEY não encontrada. Geração de imagens falhará.")
client_genai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ===================== ROTAS =====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat")
async def chat_endpoint(request: Request):
    try:
        data_req = await request.json()
        question = data_req.get("message", "").strip()
        
        # Resposta rápida para input vazio
        if not question:
            return JSONResponse({"response": "Oi! Pode mandar sua pergunta sobre minha carreira."})

        # =================================================================
        # ETAPA 1: Gerar a Resposta em Texto (Chat com Usuário) - VIA xAI
        # =================================================================
        chat = client_xai.chat.create(
            model=modelo_chat,
            messages=[
                system(FULL_SYSTEM_PROMPT),
                user(question)
            ],
        )
        response = chat.sample()
        raw_content = response.content.strip()

        # Extrai JSON da resposta da LLM
        match = re.search(r'(\{.*\})', raw_content, re.DOTALL)
        json_str = match.group(1) if match else raw_content

        try:
            answer_json = json.loads(json_str)
            answer_text = answer_json.get('resposta', raw_content)
            ctas = answer_json.get('ctas', [])
            cta_0 = ctas[0] if len(ctas) > 0 else None
            cta_1 = ctas[1] if len(ctas) > 1 else None
        except json.JSONDecodeError:
            answer_text = raw_content
            cta_0, cta_1 = None, None


        # =================================================================
        # ETAPA 2: Lógica de Geração de Imagem - VIA GOOGLE IMAGEN
        # =================================================================
        image_url = None 
        
        # Se detectou palavra-chave (ou se quiser forçar, mude para: if True:)
        if True: 
            try:
                # --- PASSO 2.1: PEDIR AO GROK PARA CRIAR O PROMPT DA IMAGEM ---
                # Isso garante que a imagem seja contextualizada e em inglês
                logger.info("Step 2.1: Solicitando ao Grok um prompt visual otimizado...")
                
                prompt_engineer_msg = (
                    f"Aja como um especialista em Engenharia de Prompt para IA Generativa (Midjourney/Imagen). "
                    f"O usuário perguntou: '{question}'. "
                    f"Crie um prompt visual descritivo, EM INGLÊS, para ilustrar esse tópico. "
                    f"Retorne APENAS o prompt em inglês."
                )

                prompt_chat = client_xai.chat.create(
                    model=modelo_chat,
                    messages=[user(prompt_engineer_msg)], 
                )
                # O prompt "traduzido" e otimizado
                imagen_prompt = prompt_chat.sample().content.strip()
                logger.info(f"Prompt Visual Gerado: {imagen_prompt}")


                # --- PASSO 2.2: ENVIAR O PROMPT OTIMIZADO PARA O GOOGLE IMAGEN ---
                logger.info("Step 2.2: Gerando imagem com Google Imagen...")

                response_img = client_genai.models.generate_images(
                    model=modelo_imagem, 
                    prompt=imagen_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="16:9",
                        # include_rai_reasoning removido para compatibilidade
                    )
                )

                # --- PASSO 2.3: CONVERTER BYTES PARA BASE64 ---
                for generated_image in response_img.generated_images:
                    image_bytes = generated_image.image.image_bytes
                    
                    # Converte bytes para string base64
                    base64_string = base64.b64encode(image_bytes).decode('utf-8')
                    
                    # Formata como Data URI
                    image_url = f"data:image/png;base64,{base64_string}"
                    logger.info("Imagem gerada e processada com sucesso.")
                    break 

            except Exception as e:
                logger.warning(f"Erro no fluxo de imagem: {e}")
                # Não quebra a requisição, apenas fica sem imagem
                image_url = None


        # =================================================================
        # ETAPA 3: Montar Resposta Final e Logs
        # =================================================================
        log_payload = {
            "event_type": "chat_interaction",
            "user_question": question,
            "ai_response": answer_text[:50] + "...", # Loga só o começo pra não poluir
            "cta_suggested": [cta_0, cta_1],
            "image_generated": bool(image_url),
            "status": "success",
            "model_text": modelo_chat,
            "model_image": modelo_imagem
        }
        logger.info(json.dumps(log_payload, ensure_ascii=False))

        return JSONResponse({
            "response": answer_text,
            "call_action0": cta_0,
            "call_action1": cta_1,
            "background_image": image_url 
        })

    except Exception as e:
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
    return {"status": "ok", "model": modelo_chat}

# Startup message
@app.on_event("startup")
async def startup_event():
    print("\n========================================")
    print("   Eleandro Gaioski - Currículo com IA")
    print("   Servidor rodando em: http://localhost:8000")
    print("========================================\n")