# 🏛️ TCE-CE Data Pipeline, Risk Engine & OCR Dashboard

Uma plataforma ponta a ponta, orientada a metadados, para **extração de dados públicos, análise de risco financeiro e auditoria antifraude**, utilizando os dados abertos do Tribunal de Contas do Estado do Ceará (TCE-CE).

Este projeto vai além de um pipeline convencional de Engenharia de Dados. Ele transforma dados brutos governamentais em inteligência acionável, combinando armazenamento otimizado em **Apache Parquet**, **motores de decisão com Machine Learning** e **Visão Computacional com OCR** para validação documental.

---

## ✨ Principais Recursos e Módulos

### ⚙️ Engenharia de Dados — Ingestion Engine

* 🚀 Extração automatizada e em massa da API do TCE-CE.
* 🔄 Arquitetura 100% orientada a metadados, utilizando o arquivo `endpoints.json`.
* 🧩 Possibilidade de adicionar novas fontes sem alterar o código Python principal.
* 🛡️ Circuit Breaker integrado para tolerância a falhas e maior resiliência contra bloqueios, instabilidades e WAF.
* 📦 Armazenamento colunar otimizado em **Apache Parquet**.

---

### 🧠 Ciência de Dados & Analytics — Risk Engine

* 📊 **Motor de Risco de Inadimplência:** avaliação preditiva de atrasos em licitações, considerando o ciclo:

```text
Empenho ➜ Liquidação ➜ Pagamento
```

* ⚙️ **Decisão Automatizada:** tradução dos escores de risco em recomendações comerciais diretas de precificação, margem de segurança e tomada de decisão.

---

### 🔎 Visão Computacional — Anti-Fraud OCR

* 👁️ **Auditoria Documental Automática:** reconciliação entre documentos físicos anexados e a base de dados oficial do TCE-CE.
* 📝 Pré-processamento de imagens com **OpenCV**.
* 🔤 Extração de texto estruturado com **PyTesseract**.
* 🔍 Uso de Regex para identificação de **CNPJ**, **valores financeiros** e informações sensíveis em documentos fiscais.

---

## 📂 Estrutura do Projeto

```text
.
├── src/
│   ├── app.py                   # Roteador do painel Streamlit
│   ├── main.py                  # Motor CLI de extração
│   └── modules/                 # Lógicas isoladas: OCR, risco, UI e banco
│
├── config/
│   ├── endpoints.json           # Dicionário dinâmico da API
│   └── municipios.json          # Mapeamento dos municípios/domínio
│
├── data/                        # Data Lake local com arquivos Parquet
│
├── docker-compose.yml           # Orquestração de contêineres
├── Dockerfile                   # Ambiente Python + dependências do sistema
└── requirements.txt             # Dependências Python
```

---

## 🚀 Como Executar — Ambiente Dockerizado

O sistema foi empacotado com Docker para garantir que dependências complexas, como os binários de Visão Computacional e OCR, rodem corretamente em diferentes sistemas operacionais sem instalar pacotes diretamente na máquina do usuário.

---

### 1. Clone o repositório

```bash
git clone https://github.com/SeuUsuario/SeuRepositorio.git
cd SeuRepositorio
```

---

### 2. Compile a infraestrutura

Na primeira execução, o Docker fará o download da imagem base, instalará as dependências do Python, o motor OCR Tesseract e demais bibliotecas necessárias:

```bash
docker compose build
```

---

### 3. Inicie o sistema

```bash
docker compose up -d
```

---

### 4. Acesse o painel de controle

Abra o navegador e acesse:

```text
http://localhost:8501
```

Caso a aplicação não abra em `localhost:8501`, execute:

```bash
docker ps
```

Em seguida, verifique a porta em que o contêiner `automacao-app` está rodando.

---

## 🎯 Funcionalidades do Dashboard

O aplicativo possui 4 módulos principais, navegáveis pelo menu superior:

### 📊 Extração

Interface para disparar extrações pontuais por:

* Município;
* Ano;
* Endpoint;
* Período de consulta.

Os dados extraídos são salvos localmente em formato **Parquet**.

---

### 🔍 Consulta

Ferramenta de auditoria visual dos arquivos Parquet extraídos, com:

* Paginação;
* Filtros dinâmicos;
* Visualização tabular;
* Consulta rápida sobre os dados armazenados no Data Lake local.

---

### 🧠 Motor de Risco

Painel voltado para análise comercial e financeira.

O usuário informa o valor da proposta e o município alvo. Em seguida, o sistema cruza o histórico de pagamentos públicos para recomendar uma margem de segurança ideal, considerando o risco de atraso no ciclo financeiro.

---

### 🔎 Auditoria OCR

Módulo para validação documental automatizada.

O usuário faz o upload de uma Nota Fiscal, recibo ou documento em imagem. O algoritmo de Visão Computacional processa os pixels, extrai os dados relevantes e realiza o cruzamento com a base do TCE-CE em busca de possíveis divergências, como:

* CNPJ divergente;
* Valor financeiro adulterado;
* Documento incompatível com os dados públicos;
* Possíveis inconsistências cadastrais.

---

## 💻 Utilização via CLI — Terminal

Para rotinas automatizadas, cronjobs ou extrações em lote sem interface gráfica, o projeto disponibiliza um Wizard Interativo via terminal:

```bash
docker compose run --rm cli
```

O contêiner será instanciado de forma interativa, executará as tarefas de rede e será removido automaticamente ao concluir a extração, garantindo melhor uso de recursos.

---

## ⚙️ Expansão Dinâmica — No-Code

A ingestão de novos dados não requer alteração direta no código Python.

Para adicionar uma nova tabela do Portal da Transparência, basta criar um novo bloco no arquivo:

```text
config/endpoints.json
```

Exemplo:

```json
{
  "Bens Incorporados ao Patrimônio": {
    "endpoint": "https://api-dados-abertos.tce.ce.gov.br/sim/bens_incorporados_...",
    "prefixo": "bens_incorporados",
    "frequencia": "intervalo_data",
    "params_obrigatorios": [
      "codigo_municipio",
      "data_inicio",
      "data_fim"
    ],
    "colunas_texto": {
      "especificacao_bem": "Especificação do Bem"
    }
  }
}
```

Após a configuração, o Streamlit e o Motor de Extração renderizarão a nova interface automaticamente.

---

## 🏗️ Tecnologias Utilizadas

### Engenharia & Dados

* Python 3.10
* Pandas
* Apache Parquet
* Requests
* JSON
* APIs REST

---

### Machine Learning & Visão Computacional

* OpenCV
* PyTesseract
* Scikit-Learn
* Regex
* OCR

---

### Infraestrutura & Interface

* Docker
* Docker Compose
* Streamlit
* CLI interativo

---

## 📌 Objetivo do Projeto

O objetivo principal deste projeto é demonstrar como dados públicos podem ser transformados em uma solução analítica completa, combinando:

* Engenharia de Dados;
* Ciência de Dados;
* Análise de risco;
* Auditoria documental;
* Automação;
* Transparência pública.

A plataforma permite extrair, organizar, consultar, auditar e interpretar dados governamentais de forma escalável, modular e orientada a decisões.

---

## 🤝 Contribuição

Sugestões, melhorias e Pull Requests são bem-vindos, especialmente para:

* Atualizações de endpoints;
* Ajustes relacionados a bloqueios ou WAF;
* Novos módulos de análise;
* Expansões do pipeline de Inteligência Artificial;
* Melhorias na interface Streamlit;
* Otimizações de performance.

---

## 📄 Licença

Este projeto foi desenvolvido com foco em transparência pública, análise de risco financeiro estruturada e auditoria documental automatizada.

Sinta-se livre para estudar, adaptar e expandir a solução conforme a necessidade do seu projeto.

---

## 👨‍💻 Autor

Desenvolvido por **Matheus Fontenele**.

GitHub: [github.com/matheFontenele](https://github.com/matheFontenele)
