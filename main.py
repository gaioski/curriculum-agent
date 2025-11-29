 
# main.py (VERSÃO DEBUG)
from fastapi import FastAPI, Request
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
import re
import base64 
from google import genai
from google.genai import types

# === CONFIGURAÇÃO INICIAL ===
load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI(title="Debug Mode")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# === CARGA DE DADOS ===
try:
    with open("data/curriculum.json", "r", encoding="utf-8") as f:
        curriculum = json.load(f)
    curriculum_text = json.dumps(curriculum, indent=2, ensure_ascii=False)
    with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()
    FULL_SYSTEM_PROMPT = f"{system_prompt}\n\nCurrículo: {curriculum_text}"
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    # Cria um dummy para não crashar o server se faltar arquivo
    FULL_SYSTEM_PROMPT = "Você é um assistente."

# === VERIFICAÇÃO DE CHAVES (IMPORTANTE) ===
XAI_KEY = os.getenv("XAI_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

print("\n--- STATUS DAS CHAVES ---")
print(f"XAI_API_KEY: {'OK' if XAI_KEY else 'FALTANDO'}")
print(f"GEMINI_API_KEY: {'OK' if GEMINI_KEY else 'FALTANDO'}")
print("-------------------------\n")

if XAI_KEY:
    client_xai = Client(api_key=XAI_KEY)
if GEMINI_KEY:
    client_genai = genai.Client(api_key=GEMINI_KEY)

# === ROTAS ===

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat_endpoint(request: Request):
    print(">>> Recebida requisição /chat")
    data_req = await request.json()
    question = data_req.get("message", "").strip()
    
    # 1. Gera Texto
    try:
        if not XAI_KEY:
            return JSONResponse({"response": "ERRO: Configure XAI_API_KEY no .env"})

        chat = client_xai.chat.create(
            model="grok-4-1-fast-reasoning",
            messages=[system(FULL_SYSTEM_PROMPT), user(question)],
        )
        response = chat.sample()
        raw_content = response.content.strip()
        
        # Limpeza básica do JSON
        match = re.search(r'(\{.*\})', raw_content, re.DOTALL)
        json_str = match.group(1) if match else raw_content
        try:
            answer_json = json.loads(json_str)
            answer_text = answer_json.get('resposta', raw_content)
        except:
            answer_text = raw_content

    except Exception as e:
        print(f"ERRO NO GROK: {e}")
        return JSONResponse({"response": f"Erro no backend: {str(e)}"})

    # 2. Gatilho de Imagem (FORÇADO PARA TRUE PARA TESTE)
    # Mude para True para garantir que o front receba a ordem
    should_generate = True 
    print(f">>> Enviando resposta de texto. Gatilho de imagem: {should_generate}")

    return JSONResponse({
        "response": answer_text,
        "trigger_image": should_generate
    })


@app.post("/generate_background")
async def generate_background_endpoint(request: Request):
    print(">>> Recebida requisição /generate_background (Imagem)")
    data_req = await request.json()
    question = data_req.get("message", "")

    if not GEMINI_KEY:
        print("ERRO: Tentou gerar imagem mas GEMINI_API_KEY está faltando.")
        return JSONResponse({"error": "Sem chave Gemini"}, status_code=400)

    try:
        # 1. Prompt
        print("   1. Gerando Prompt visual com Grok...")
        prompt_msg = f"Create a detailed English prompt for a photorealistic background image about: '{question}'. No text in image."
        prompt_chat = client_xai.chat.create(
            model="grok-4-1-fast-reasoning",
            messages=[user(prompt_msg)], 
        )
        imagen_prompt = prompt_chat.sample().content.strip()
        print(f"   Prompt Gerado: {imagen_prompt}")

        # 2. Imagem
        print("   2. Chamando Google Imagen...")
        response_img = client_genai.models.generate_images(
            model="imagen-4.0-fast-generate-001", # Verifique se sua conta aceita este ou o 4.0
            prompt=imagen_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
            )
        )

        # 3. Base64
        print("   3. Convertendo imagem...")
        for generated_image in response_img.generated_images:
            image_bytes = generated_image.image.image_bytes
            base64_string = base64.b64encode(image_bytes).decode('utf-8')
            print(">>> SUCESSO! Imagem retornada.")
            return JSONResponse({"image_url": f"data:image/png;base64,{base64_string}"})

    except Exception as e:
        print(f"!!! ERRO CRÍTICO NA GERAÇÃO DE IMAGEM: {e}")
        # Retorna o erro para o front ver
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({"image_url": None})

# Startup
@app.on_event("startup")
async def startup_event():
    print("\n================ DEBUG MODE ON ================")
    print("Acesse http://localhost:8000")
    print("Observe este terminal para ver os erros!")
    print("===============================================\n")