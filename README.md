# TCE-CE Data Extractor

Este projeto consiste em uma ferramenta de automação desenvolvida em Python para extração, processamento e exportação de dados financeiros a partir da API de Dados Abertos do Tribunal de Contas do Estado do Ceará (TCE-CE).

## Funcionalidades
- **Extração Automatizada:** Coleta dados de Notas de Empenho, Notas Fiscais e Itens de Notas Fiscais.
- **Abrangência:** Varredura completa por município e por período (mensal/anual).
- **Exportação Flexível:** Os dados são salvos automaticamente em formato **CSV** (para análise em Power BI/Excel) e **JSON** (para consumo em aplicações).
- **Tratamento de Dados:** Utilização da biblioteca `pandas` para estruturação e manipulação dos DataFrames.

## Tecnologias Utilizadas
- **Python 3**
- **Requests:** Para requisições HTTP à API do TCE-CE.
- **Pandas:** Para manipulação e exportação de dados.
- **JSON:** Para entrada de configuração e saída de dados estruturados.

## Pré-requisitos
Certifique-se de ter o Python instalado e um ambiente virtual configurado:


### Clone o repositório
```bash
git clone [https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git](https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git)
```

### Crie o ambiente virtual

```bash
python -m venv venv
source venv/bin/activate
```

### Instale as dependências
```bash
pip install pandas requests
```

## Estrutura do projeto
- main.py: Script principal contendo a lógica de extração e salvamento.
- municipios.json: Arquivo de entrada contendo a lista de municípios a serem consultados.
- output/: (Pasta gerada automaticamente) Destino dos arquivos CSV e JSON extraídos.

### Como Executar
- Certifique-se de que o arquivo municipios.json esteja na raiz do projeto seguindo a estrutura esperada (lista de municípios com codigo_municipio).
- Execute o script principal:
  ```
  python main.py
  ```

### Notas de Desenvolvimento
- O script gerencia a latência da API com time.sleep para evitar bloqueios de requisição.
- A estrutura de dados baseia-se no endpoint de Dados Abertos do TCE-CE. Caso precise adaptar para outros endpoints, basta ajustar os parâmetros na função extrair_dados.

  ---

  Desenvolvido por Matheus Fontenele
