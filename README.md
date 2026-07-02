# 🏛️ TCE-CE Ingestion Engine & Dashboard

Uma plataforma automatizada e orientada a metadados para **extração, consolidação e visualização de dados abertos** do Tribunal de Contas do Estado do Ceará (TCE-CE).

O projeto utiliza uma arquitetura resiliente, com **Circuit Breaker**, tratamento automático de falhas, estratégias de contorno de bloqueios (WAF) e armazenamento em formato **Apache Parquet**, permitindo a ingestão eficiente de grandes volumes de dados para análises posteriores.

---

# ✨ Principais Recursos

- 🚀 Extração automatizada dos Dados Abertos do TCE-CE
- 📦 Armazenamento otimizado em formato **Apache Parquet**
- 🔄 Arquitetura orientada a metadados (`endpoints.json`)
- 🛡️ Circuit Breaker para tolerância a falhas
- ⚡ Pipeline escalável para novas fontes de dados
- 📊 Dashboard interativo desenvolvido com Streamlit
- 🐳 Execução totalmente containerizada com Docker

---

# 📂 Estrutura do Projeto

```text
.
├── app/                 # Interface Streamlit
├── cli/                 # Assistente de Terminal
├── core/                # Motor de extração
├── config/
│   └── endpoints.json   # Configuração dinâmica dos endpoints
├── data/                # Arquivos Parquet gerados
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

# 🚀 Como Executar

## Pré-requisitos

Antes de iniciar, certifique-se de possuir instalado:

- Docker

---

## Usuários Finais (Dashboard)

O sistema é executado integralmente através do **Docker**, garantindo um ambiente padronizado e simplificando a instalação.

### 1. Clone o repositório

```bash
git clone https://github.com/matheFontenele/Automacao-TCE.git
cd automacao_api_tse
```

### 2. Compile a imagem

Na primeira execução (ou sempre que houver alterações no código ou nas dependências), execute:

```bash
docker compose build
```

### 3. Inicie o sistema

```bash
docker compose up -d
```

Esse comando iniciará todos os serviços necessários em segundo plano.

### 4. Acesse o Dashboard

Abra seu navegador e acesse:

```text
http://localhost:8501
```

A interface permitirá:

- 📥 Executar novas extrações de dados
- 🗂️ Navegar pelos datasets armazenados
- 🔍 Auditar informações extraídas
- 📊 Visualizar os dados ingeridos

Todos os arquivos são armazenados automaticamente na pasta:

```text
data/
```

> **⚠️ O Dashboard não abriu em `http://localhost:8501`?**
>
> Verifique se o container da aplicação está em execução:
>
> ```bash
> docker ps
> ```
>
> Localize o container **`automacao-app`** e observe a coluna **PORTS**, que informa em qual porta o Streamlit foi publicado.
>
> Exemplo:
>
> ```text
> CONTAINER ID   IMAGE             PORTS
> a1b2c3d4e5f6   automacao-app      0.0.0.0:8502->8501/tcp
> ```
>
> Nesse caso, o Dashboard deverá ser acessado em:
>
> ```text
> http://localhost:8502
> ```
>
> Se o container **`automacao-app`** não estiver em execução, verifique os logs para identificar o problema:
>
> ```bash
> docker compose logs app
> ```

### 5. Encerrar a aplicação

Quando finalizar o uso:

```bash
docker compose down
```

Esse comando interrompe os containers mantendo os dados persistidos nos volumes configurados.

---

# 💻 Utilização via CLI

Além da interface web, o projeto disponibiliza um **Assistente de Terminal (CLI)**, ideal para testes, depuração e execuções pontuais.

Execute:

```bash
docker compose run --rm cli
```

O CLI permite realizar extrações específicas sem a necessidade de iniciar o Dashboard.

---

# ⚙️ Expansão Dinâmica

Toda a arquitetura foi desenvolvida para ser **orientada a metadados**.

Isso significa que **não é necessário alterar o código Python para adicionar novos endpoints da API do TCE-CE**.

Basta adicionar uma nova entrada ao arquivo:

```text
config/endpoints.json
```

---

# Exemplo de Endpoint

```json
"Bens Incorporados ao Patrimônio": {
  "endpoint": "https://api-dados-abertos.tce.ce.gov.br/sim/bens_incorporados_patrimonio_municipio",
  "prefixo": "bens_incorporados_patrimonio_municipio",
  "frequencia": "intervalo_data",
  "params_obrigatorios": [
    "codigo_municipio",
    "data_inicio",
    "data_fim"
  ],
  "colunas_texto": {
    "especificacao_bem": "Especificação do Bem",
    "numero_tombamento": "Nº Tombamento"
  },
  "layout_card": {
    "topo_esq": "numero_tombamento",
    "titulo_grande": "especificacao_bem",
    "meta_1": "municipio_referencia",
    "meta_2": "data_incorporacao",
    "corpo_texto": "descricao_bem",
    "grid_financeiro": [
      {
        "coluna": "valor_bruto",
        "label_caixa": "Valor de Incorporação"
      }
    ]
  }
}
```

---

# 📖 Dicionário de Configuração

| Campo | Descrição |
|--------|-----------|
| `endpoint` | URL oficial da API do TCE-CE |
| `prefixo` | Prefixo utilizado na geração dos arquivos `.parquet` |
| `frequencia` | Estratégia utilizada para percorrer períodos de consulta |
| `params_obrigatorios` | Parâmetros exigidos pelo endpoint |
| `colunas_texto` | Define colunas que devem ser exibidas como texto |
| `layout_card` | Configuração automática dos cards do Dashboard |

---

# 📅 Frequências Disponíveis

| Valor | Descrição |
|--------|-----------|
| `mensal` | Consulta mês a mês |
| `anual` | Consulta por exercício |
| `intervalo_data` | Consulta utilizando data inicial e final |

---

# ⚠️ Boas Práticas

### Endpoints Financeiros

Normalmente exigem:

```text
exercicio_orcamento
```

Exemplos:

- Empenhos
- Pagamentos
- Liquidações

---

### Endpoints Patrimoniais

Normalmente utilizam:

```text
data_referencia_doc
```

ou

```text
data_inicio
data_fim
```

Exemplos:

- Veículos
- Imóveis
- Patrimônio

---

# ✔️ Validação

Após adicionar um novo endpoint, recomenda-se realizar um teste utilizando o CLI:

```bash
docker compose run --rm cli
```

Caso a API retorne:

```text
400 Bad Request
```

Verifique principalmente o campo:

```json
params_obrigatorios
```

---

# 🏗️ Tecnologias Utilizadas

- Python
- Streamlit
- Pandas
- DuckDB
- Apache Parquet
- Docker
- Docker Compose
- Requests
- SQL
- JSON

---

# 🤝 Contribuindo

Sugestões, melhorias e correções são sempre bem-vindas.

Caso identifique alterações na API do TCE-CE, mudanças de rotas, novos mecanismos de proteção ou queira contribuir com novas funcionalidades, abra uma **Issue** ou envie um **Pull Request**.

---

# 📄 Licença

Este projeto foi desenvolvido para automatizar a ingestão, organização e visualização de dados públicos disponibilizados pelo Tribunal de Contas do Estado do Ceará.