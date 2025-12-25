# Base enxuta e compatível com opencv
FROM python:3.10-slim

# Evita prompts interativos
ENV DEBIAN_FRONTEND=noninteractive

# Dependências do sistema (opencv + zxing)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libzbar0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Diretório da app
WORKDIR /app

# Copia tudo
COPY . /app

# Atualiza pip
RUN pip install --no-cache-dir --upgrade pip

# Instala dependências Python
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    numpy \
    opencv-python-headless \
    zxing-cpp \
    httpx \
    pydantic-settings

# Porta padrão (Coolify detecta)
EXPOSE 8000

# Comando de start
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]