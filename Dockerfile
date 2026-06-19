# Usa uma imagem leve de Python
FROM python:3.10-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Instala dependências do sistema necessárias para algumas libs (como o pandas/pyarrow)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências primeiro (otimização de cache do Docker)
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# ✅ COPIA APENAS O CÓDIGO FONTE (não copia data/ nem data_internal/)
COPY src/ ./src/
COPY municipios.json .

# Expõe a porta do Streamlit
EXPOSE 8501

# ✅ COMANDO AJUSTADO para nova estrutura (src/app.py)
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]