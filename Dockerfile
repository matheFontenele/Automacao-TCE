# Usa uma imagem leve de Python
FROM python:3.10-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Instala dependências do sistema (Essencial para OCR e OpenCV)
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências primeiro (otimização de cache do Docker)
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos de configuração
COPY municipios.json .
COPY endpoints.json .

# Copia apenas o código fonte
COPY src/ ./src/

# Expõe a porta do Streamlit
EXPOSE 8501

# Comando padrão para subir o Streamlit
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]