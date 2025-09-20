FROM python:3.11-slim

# Instala dependências do Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    wget \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk1.0-0 \
    libcairo2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Variáveis de ambiente padrão
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PYTHONUNBUFFERED=1
ENV HEADLESS=1
ENV USER_DATA_DIR=/app/user_data

WORKDIR /app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do bot
COPY . .

# Comando padrão: inicia FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
