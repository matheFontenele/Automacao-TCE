# 🏛️ TCE-CE Ingestion Engine & Dashboard

Uma plataforma automatizada e orientada a metadados para extração, consolidação e visualização de dados abertos do Tribunal de Contas do Estado do Ceará (TCE-CE). 

Este sistema utiliza uma arquitetura resiliente (com *Circuit Breakers* e contorno de WAF) para baixar dados governamentais em larga escala, salvando-os em formato otimizado `.parquet` para análises avançadas.

---

## 🚀 Como Utilizar (Usuários Finais)

Para iniciar o sistema e acessar o Painel de Controle:

1. Abra a pasta raiz deste projeto.
2. Dê um **duplo clique** no arquivo `run.bat`.
3. Aguarde o terminal carregar as dependências em segundo plano.
4. O navegador abrirá automaticamente o **Painel de Controle** (Streamlit).
5. **No Painel:**
   - **Extração:** Selecione o município e os parâmetros desejados para forçar uma nova extração.
   - **Visualização:** Navegue pelas abas superiores para auditar os dados ingeridos.
   - Os arquivos extraídos ficam armazenados de forma persistente na pasta `data/`.

---

## 💻 Como Utilizar (Desenvolvedores / CLI)

O sistema conta com um Assistente de Terminal (CLI) conteinerizado, ideal para extrações cirúrgicas sem precisar subir a interface gráfica.

Para evocar o terminal interativo via Docker:
```bash
docker compose run --rm cli