# Stage 1: Builder (instala deps)
FROM python:3.10-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime (leve)
FROM python:3.10-slim

WORKDIR /app

# Copia deps do builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia código
COPY . .

# Expõe $PORT (padrão 8080 no GCP)
EXPOSE $PORT

# CMD dinâmico: usa $PORT (8080 no GCP, 8000 local se você setar)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $${PORT:-8000}"]