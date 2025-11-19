# 1. Usa uma imagem leve do Python
FROM python:3.10-slim

# 2. Define a pasta de trabalho dentro do container
WORKDIR /app

# 3. Copia o arquivo de requisitos e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia o restante do seu código para dentro do container
COPY . .

# 5. Comando para iniciar o FastAPI
# O Google Cloud Run define a variável de ambiente $PORT automaticamente
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}