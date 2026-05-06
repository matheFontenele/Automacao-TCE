import streamlit as st
import pandas as pd
import os
import glob
import re
from main import executar_pipeline, carregar_municipios

def render_extraction_page():
    # --- SIDEBAR (CONFIGURAÇÕES) ---
    with st.sidebar:
        st.header("Configurações")
        
        # Salvando inputs no session_state para persistir entre as abas/páginas
        if 'ano_input' not in st.session_state: st.session_state.ano_input = 2025
        st.session_state.ano_input = st.number_input("Ano Base", min_value=2000, max_value=2030, value=st.session_state.ano_input)

        lista_municipios = carregar_municipios()
        opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}
        
        if 'mun_input' not in st.session_state: st.session_state.mun_input = "Todos"
        st.session_state.mun_input = st.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))

        if 'mes_input' not in st.session_state: st.session_state.mes_input = "Todos"
        st.session_state.mes_input = st.selectbox("Mês de Extração", options=["Todos"] + list(range(1, 13)))

        if st.button("Executar Extração"):
            log_container = st.empty()
            log_messages = []
            def stream_log(msg):
                log_messages.append(msg)
                log_container.code("\n".join(log_messages[-50:]))

            municipio_selecionado = None if st.session_state.mun_input == "Todos" else opcoes_mun[st.session_state.mun_input]
            with st.spinner("Buscando dados no TCE..."):
                executar_pipeline(st.session_state.ano_input, mes_selecionado=st.session_state.mes_input, municipio_selecionado=municipio_selecionado, log_func=stream_log)
                st.success("Extração concluída!")

    # --- ÁREA PRINCIPAL ---
    st.header("Visualizar Dados")
    
    def carregar_e_exibir_dados(tipo_dado):
    # 1. Recuperar valores do session_state
    ano = st.session_state.ano_input
    mes = st.session_state.mes_input
    mun = st.session_state.mun_input

    # 2. Configurar wildcards (curingas) para busca
    ano_str = "*" if ano == "Todos" else str(ano)
    mes_str = "*" if mes == "Todos" else str(mes).zfill(2)
    
    if mun == "Todos":
        mun_str = "*"
    else:
        # Extrai o código entre parênteses: "CRATO (049)" -> "049"
        match = re.search(r'\((\d+)\)', mun)
        mun_str = match.group(1) if match else "*"

    # 3. Determinar o padrão de nome do arquivo
    if "itens_notas_fiscais" in tipo_dado:
        padrao = os.path.join('data', f"{tipo_dado}_{ano_str}_{mun_str}.parquet")
    else:
        # Padrão para arquivos mensais
        padrao = os.path.join('data', f"{tipo_dado}_{ano_str}_{mes_str}_{mun_str}.parquet")

    arquivos = glob.glob(padrao)

    # Debug visual
    with st.expander("Ver detalhes da busca"):
        st.write(f"Padrão de busca: `{padrao}`")
        st.write(f"Arquivos encontrados: {len(arquivos)}")

    if not arquivos:
        st.warning(f"Nenhum arquivo encontrado para estes filtros.")
        return

    # 4. Botão de carga dinâmica
    if st.button(f"Carregar {len(arquivos)} arquivos", key=f"btn_{tipo_dado}"):
        with st.spinner("Consolidando dados..."):
            try:
                # Carrega todos os arquivos encontrados
                df_lista = [pd.read_parquet(f) for f in arquivos]
                df = pd.concat(df_lista, ignore_index=True)
                
                # Garante que tudo seja texto para evitar conflitos de tipos
                df = df.astype(str)

                st.success(f"Sucesso! {len(df)} registros carregados.")
                st.dataframe(df, use_container_width=True)

                # Download
                st.download_button(
                    label="Baixar consolidado (CSV)",
                    data=df.to_csv(index=False, sep=';').encode('utf-8-sig'),
                    file_name=f"export_{tipo_dado}_{ano_str}.csv",
                    mime='text/csv'
                )
            except Exception as e:
                st.error(f"Erro ao carregar arquivos: {e}")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Notas de Empenho", "Notas Fiscais", "Notas de Pagamento", "Pagamento e Liquidações", "Liquidações", "Itens de Notas Fiscais"])
    with tab1: carregar_e_exibir_dados("notas_empenho")
    with tab2: carregar_e_exibir_dados("notas_fiscais")
    with tab3: carregar_e_exibir_dados("notas_pagamentos")
    with tab4: carregar_e_exibir_dados("Pagamento e Liquidações")
    with tab5: carregar_e_exibir_dados("liquidacoes")
    with tab6: carregar_e_exibir_dados("itens_notas_fiscais")