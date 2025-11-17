from xai_sdk import Client
from xai_sdk.chat import user, system
from dotenv import load_dotenv
import json
import os

load_dotenv()

# Carregar currículo
with open("data/curriculum.json", "r", encoding="utf-8") as f:
    curriculum = json.load(f)

# System prompt
system_prompt = open("prompts/system_prompt.txt", "r", encoding="utf-8").read()
curriculum_text = json.dumps(curriculum, indent=2, ensure_ascii=False)

# Cliente xAI (Grok 4)
client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    timeout=3600  # Para modelos de raciocínio longos
)

print("Agente impulsionado por Inteligência Artifical de Currículo do Eleandro Gaioski")
print("Pergunte sobre minha carreira (ou 'sair')\n")

while True:
    question = input("Você: ").strip()
    if question.lower() in ["sair", "exit", "quit"]:
        print("Até logo!")
        break
    if not question:
        continue

    # Criar chat novo para cada pergunta (stateless, simples)
    chat = client.chat.create(model="grok-4-fast-reasoning")  # Ou "grok-4-fast" para mais velocidade

    # Adicionar mensagens
    chat.append(system(f"{system_prompt}\n\nCurrículo:\n{curriculum_text}"))
    chat.append(user(question))

    try:
        response = chat.sample()
        print(f"\nEleandro Gaioski: {response.content}\n")
    except Exception as e:
        print(f"Erro: {e}")
        # Fallback para Groq se quiser
        # from langchain_groq import ChatGroq
        # llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))
        # ... (adicione o código LangChain aqui se precisar)