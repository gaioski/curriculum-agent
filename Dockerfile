FROM python:3.10-slim

WORKDIR /app

# Instala dependências do sistema (caso precise)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements primeiro (melhor cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# VARIÁVEL OBRIGATÓRIA do Cloud Run
ENV PORT=8080

RUN pip install --no-cache-dir -r requirements.txt

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}