# Stage 1: Builder (instala deps)
FROM python:3.10-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime (leve, sem GCP)
FROM python:3.10-slim

WORKDIR /app

# Copia só o necessário do builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia código do app
COPY . .

# Expõe porta
EXPOSE 8000

# Roda com uvicorn (sem reload pra prod)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]