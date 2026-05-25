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

# Copia todo o resto do projeto para dentro do contêiner
COPY . .

# Expõe a porta do Streamlit
EXPOSE 8501

# Comando atualizado para desenvolvimento: monitoramento ativo via Polling
CMD ["streamlit", "run", "app.py", "--server.runOnSave", "true", "--server.fileWatcherType", "poll"]