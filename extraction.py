import streamlit as st
import pandas as pd
import os
import glob
import re
from main import executar_pipeline, carregar_municipios

# Mapeamento para garantir que o nome da aba encontre o arquivo correto no disco
DATA_MAP = {
    "Notas de Empenho": "notas_empenho",
    "Notas Fiscais": "notas_fiscais",
    "Notas de Pagamento": "notas_pagamentos",
    "Pagamento e Liquidações": "pagamento_e_liquidacoes",
    "Liquidações": "liquidacoes",
    "Itens de Notas Fiscais": "itens_notas_fiscais"
}

def render_extraction_page():
    # --- SIDEBAR (CONFIGURAÇÕES) ---
    with st.sidebar:
        st.header("Configurações")
        
        # Persistência de estado
        if 'ano_input' not in st.session_state: 
            st.session_state.ano_input = 2025
            
        st.session_state.ano_input = st.number_input(
            "Ano Base", 
            min_value=2000, 
            max_value=2030, 
            value=st.session_state.ano_input
        )

        lista_municipios = carregar_municipios()
        opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}
        
        if 'mun_input' not in st.session_state: 
            st.session_state.mun_input = "Todos"
        
        st.session_state.mun_input = st.selectbox(
            "Município", 
            options=["Todos"] + list(opcoes_mun.keys())
        )

        if 'mes_input' not in st.session_state: 
            st.session_state.mes_input = "Todos"
            
        st.session_state.mes_input = st.selectbox(
            "Mês de Extração", 
            options=["Todos"] + list(range(1, 13))
        )

        if st.button("Executar Extração"):
            log_container = st.empty()
            log_messages = []
            
            def stream_log(msg):
                log_messages.append(msg)
                log_container.code("\n".join(log_messages[-50:]))

            municipio_selecionado = None if st.session_state.mun_input == "Todos" else opcoes_mun[st.session_state.mun_input]
            
            with st.spinner("Buscando dados no TCE..."):
                executar_pipeline(
                    st.session_state.ano_input, 
                    mes_selecionado=st.session_state.mes_input, 
                    municipio_selecionado=municipio_selecionado, 
                    log_func=stream_log
                )
                st.success("Extração concluída!")

    # --- ÁREA PRINCIPAL ---
    st.header("Visualizar Dados")

    def carregar_e_exibir_dados(tipo_arquivo_prefixo):
        # 1. Recuperar valores dos filtros na Sidebar
        ano = st.session_state.ano_input
        mes = st.session_state.mes_input
        mun = st.session_state.mun_input

        # 2. Configurar os curingas para a busca
        ano_str = str(ano)
        mes_str = "*" if mes == "Todos" else str(mes).zfill(2)
    
        if mun == "Todos":
            mun_pattern = "*"
        else:
            match = re.search(r'\((\d+)\)', mun)
            mun_pattern = match.group(1) if match else "*"

        # Define o padrão de busca baseado no tipo de documento
        if "itens_notas_fiscais" in tipo_arquivo_prefixo:
            nome_busca = f"{tipo_arquivo_prefixo}_{ano_str}_{mun_pattern}.parquet"
        else:
            nome_busca = f"{tipo_arquivo_prefixo}_{ano_str}_{mes_str}_{mun_pattern}.parquet"

        padrao = os.path.join('data', nome_busca)
        arquivos_encontrados = sorted(glob.glob(padrao))

        # --- INTERFACE DE SELEÇÃO DE ARQUIVO ---
        if arquivos_encontrados:
            st.success(f"Encontrados {len(arquivos_encontrados)} arquivos para o ano {ano_str}.")
        
            nomes_arquivos = [os.path.basename(f) for f in arquivos_encontrados]
            arquivo_selecionado_nome = st.selectbox(
                f"Selecione o arquivo de {tipo_arquivo_prefixo}:",
                options=nomes_arquivos,
                key=f"select_{tipo_arquivo_prefixo}_{ano}"
            )

            caminho_completo = os.path.join('data', arquivo_selecionado_nome)

            if st.button(f"📄 Abrir {arquivo_selecionado_nome}", key=f"btn_view_{tipo_arquivo_prefixo}"):
                try:
                    df = pd.read_parquet(caminho_completo)
                
                    st.divider()
                    st.subheader(f"Visualizando: {arquivo_selecionado_nome}")
                    st.caption(f"Total de registros: {len(df):,}")

                    st.dataframe(df.head(500), use_container_width=True)
                
                    if len(df) > 500:
                        st.info("💡 Mostrando as primeiras 500 linhas para performance.")

                    st.download_button(
                        label="📥 Baixar este arquivo (CSV)",
                        data=df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig'),
                        file_name=arquivo_selecionado_nome.replace('.parquet', '.csv'),
                        mime='text/csv',
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo: {e}")
        else:
            st.warning(f"Nenhum arquivo de `{tipo_arquivo_prefixo}` encontrado para o ano {ano_str}.")
            st.info("Ajuste o 'Ano Base' na barra lateral.")

    # Criação dinâmica das abas
    abas = st.tabs(list(DATA_MAP.keys()))
    
    for i, nome_aba in enumerate(DATA_MAP.keys()):
        with abas[i]:
            carregar_e_exibir_dados(DATA_MAP[nome_aba])