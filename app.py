import streamlit as st
import pandas as pd
import os
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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Notas de Empenho", "Notas Fiscais", "Notas de Pagamento", "Liquidações", "Itens de Notas Fiscais"])

def exibir_csv(tipo_dado):
    # Lista arquivos na pasta 'data'
    if not os.path.exists('data'):
        st.warning("Pasta 'data' não encontrada.")
        return

    arquivos = [f for f in os.listdir('data') if tipo_dado in f and f.endswith('.csv')]
    
    if not arquivos:
        st.warning(f"Nenhum arquivo de {tipo_dado} encontrado. Realize a extração primeiro.")
        return

    arquivo_selecionado = st.selectbox(f"Selecione o arquivo de {tipo_dado}:", arquivos, key=tipo_dado)
    
    if st.button(f"Carregar {arquivo_selecionado}", key=f"btn_{arquivo_selecionado}"):
        df = pd.read_csv(os.path.join('data', arquivo_selecionado), sep=';', encoding='utf-8-sig')
        st.dataframe(df, use_container_width=True)

with tab1:
    exibir_csv("notas_empenho")

with tab2:
    exibir_csv("notas_fiscais")