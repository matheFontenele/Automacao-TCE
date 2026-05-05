import re
import streamlit as st
import pandas as pd
import os
import glob
from main import executar_pipeline, carregar_municipios

st.set_page_config(page_title="Automação TCE-CE", layout="wide")

st.title("🚀 Painel de Automação TCE-CE")

# Sidebar: Entrada de dados e Extração
with st.sidebar:
    st.header("Configurações")
    ano_input = st.number_input("Ano Base", min_value=2000, max_value=2030, value=2025)
    
    # Lógica do Selectbox de Municípios
    lista_municipios = carregar_municipios()

    # Dicionário para mapear "Nome (Código)" -> Objeto do Município
    opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}

    mun_input = st.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
    
    mes_opcoes = ["Todos"] + list(range(1, 13))
    mes_input = st.selectbox("Mês de Extração", options=mes_opcoes)
    
    if st.button("Executar Extração"):
        # 1. Cria um container vazio para os logs aparecerem
        log_container = st.empty()
        log_messages = []

        # 2. Define a função que o main.py vai chamar
        def stream_log(msg):
            log_messages.append(msg)
            log_container.code("\n".join(log_messages[-50:]))

        # Filtra o município se não for "Todos"
        municipio_selecionado = None if mun_input == "Todos" else opcoes_mun[mun_input] 

        # 3. Chama o pipeline passando a nossa função de log
        with st.spinner("Buscando dados no TCE..."):
            executar_pipeline(ano_input, mes_selecionado=mes_input, municipio_selecionado=municipio_selecionado, log_func=stream_log)
            st.success("Extração concluída!")

# Visualização de Dados (Tabs)
st.header("Visualizar Dados")
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Notas de Empenho", "Notas Fiscais", "Notas de Pagamento", "Pagamento e Liquidações", "Liquidações", "Itens de Notas Fiscais"])

def carregar_e_exibir_dados(tipo_dado):
    # 1. Obter o código do município selecionado
    if mun_input == "Todos":
        mun_code = "*"
    else:
        # Extrai o código entre parênteses: "CRATO (049)" -> "049"
        match = re.search(r'\((\d+)\)', mun_input)
        mun_code = match.group(1) if match else "*"

    # 2. Obter o mês
    mes_str = "*" if mes_input == "Todos" else str(mes_input).zfill(2)

    # 3. Construir o padrão de busca
    padrao = os.path.join('data', f"{tipo_dado}_{ano_input}_{mes_str}_{mun_code}.parquet")
    arquivos = glob.glob(padrao)
    
    st.write(f"Buscando: {padrao}") # Ajuda a debugar o que está procurando

    if not arquivos:
        st.warning(f"Nenhum arquivo encontrado para estes filtros: {ano_input} / {mes_input} / {mun_code}")
        return

    # 4. Botão de carga dinâmica
    if st.button(f"Filtrar e Carregar ({len(arquivos)} arquivos)", key=f"btn_{tipo_dado}"):
        with st.spinner("Carregando e consolidando..."):
            df = pd.concat([pd.read_parquet(f) for f in arquivos], ignore_index=True)
            df = df.astype(str)
            
            st.success(f"Carregados {len(df)} registros!")
            st.dataframe(df, use_container_width=True)
            
            # Botão de download do que foi filtrado
            st.download_button(
                label="Baixar resultado filtrado (CSV)",
                data=df.to_csv(index=False, sep=';').encode('utf-8-sig'),
                file_name=f"dados_filtrados_{tipo_dado}.csv",
                mime='text/csv',
                key=f"download_{tipo_dado}" # Você já tinha esse, está correto!
            )

with tab1:
    carregar_e_exibir_dados("notas_empenho")

with tab2:
    carregar_e_exibir_dados("notas_fiscais")

with tab3:
    carregar_e_exibir_dados("notas_pagamentos")

with tab4:
    carregar_e_exibir_dados("liquidacoes")