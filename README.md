# 🏛️ TCE-CE Ingestion Engine & Dashboard

Uma plataforma automatizada e orientada a metadados para **extração, consolidação e visualização de dados abertos** do Tribunal de Contas do Estado do Ceará (TCE-CE).

O projeto utiliza uma arquitetura resiliente, com **Circuit Breaker**, tratamento automático de falhas, estratégias de contorno de bloqueios (WAF) e armazenamento em formato **Apache Parquet**, permitindo ingestão eficiente de grandes volumes de dados para análises posteriores.

---

# ✨ Principais Recursos

- 🚀 Extração automatizada dos Dados Abertos do TCE-CE
- 📦 Armazenamento otimizado em formato **Parquet**
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
├── cli/                 # Assistente de terminal
├── core/                # Motor de extração
├── config/
│   └── endpoints.json   # Configuração dinâmica
├── data/                # Arquivos Parquet
├── docker-compose.yml
└── run.bat
```

---

# 🚀 Como Executar

## Usuários Finais

Para iniciar o sistema:

1. Abra a pasta raiz do projeto.
2. Execute o arquivo:

```text
run.bat
```

3. Aguarde a inicialização.

4. O navegador abrirá automaticamente o Dashboard.

---

## Funcionalidades do Painel

### Extração

- Seleção de município
- Escolha do endpoint
- Definição do período
- Execução manual da coleta

### Visualização

- Navegação pelos datasets
- Auditoria dos dados
- Consulta aos arquivos armazenados

Todos os dados são persistidos automaticamente na pasta:

```text
data/
```

---

# 💻 Utilização via CLI

Também é possível utilizar apenas o mecanismo de extração através do terminal.

```bash
docker compose run --rm cli
```

Essa opção é recomendada para:

- testes;
- depuração;
- novas integrações;
- execução automatizada.

---

# ⚙️ Expansão Dinâmica

Toda a arquitetura é orientada por metadados.

Isso significa que **não é necessário alterar o código Python para adicionar novos endpoints da API do TCE-CE.**

Basta adicionar uma nova entrada no arquivo:

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
| `endpoint` | URL oficial da API |
| `prefixo` | Nome base dos arquivos Parquet |
| `frequencia` | Estratégia de iteração temporal |
| `params_obrigatorios` | Parâmetros exigidos pela API |
| `colunas_texto` | Colunas exibidas como texto |
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

## Tabelas Financeiras

Normalmente exigem:

```text
exercicio_orcamento
```

Exemplos:

- Empenhos
- Pagamentos
- Liquidações

---

## Tabelas Patrimoniais

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
- Bens Patrimoniais

---

# ✔️ Validação

Após adicionar um novo endpoint, recomenda-se testar utilizando o CLI.

```bash
docker compose run --rm cli
```

Caso a API retorne:

```text
400 Bad Request
```

verifique principalmente o campo:

```json
params_obrigatorios
```

---

# 🏗️ Tecnologias Utilizadas

- Python
- Streamlit
- DuckDB
- Pandas
- Apache Parquet
- Docker
- Docker Compose
- Requests
- SQL
- JSON

---

# 🤝 Contribuição

Sugestões, melhorias e correções são bem-vindas.

Caso identifique alterações na API do TCE-CE, mudanças de rotas ou novos mecanismos de proteção (WAF), abra uma **Issue** ou envie um **Pull Request**.

---

# 📄 Licença

Este projeto foi desenvolvido para fins de automação, integração e análise de dados públicos disponibilizados pelo Tribunal de Contas do Estado do Ceará.