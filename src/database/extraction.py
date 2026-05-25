import streamlit as st
import pandas as pd
import os
import glob
import re
import time
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
    # --- INICIALIZAÇÃO DO ESTADO GLOBAL DOS LOGS E ARQUIVOS ---
    if 'log_messages' not in st.session_state:
        st.session_state.log_messages = []
    if 'arquivos_criados' not in st.session_state:
        st.session_state.arquivos_criados = []

    # --- SIDEBAR (CONFIGURAÇÕES) ---
    with st.sidebar:
        st.header("Configurações")
        
        # Criando a lista de anos de 2008 até 2026
        anos_disponiveis = list(range(2008, 2027))
        
        # Persistência de estado do Ano
        if 'ano_input' not in st.session_state: 
            st.session_state.ano_input = 2025  # Ano padrão inicial
            
        # Garante que o valor salvo no state existe na lista de anos para não gerar erro no selectbox
        default_index = anos_disponiveis.index(st.session_state.ano_input) if st.session_state.ano_input in anos_disponiveis else len(anos_disponiveis) - 1

        # Substituído st.number_input por st.selectbox
        st.session_state.ano_input = st.selectbox(
            "Ano Base", 
            options=anos_disponiveis,
            index=default_index
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

        # Botão para Executar a Extração
        btn_extrair = st.button("Executar Extração", use_container_width=True)

        # --- ÁREA DE LOGS E ARQUIVOS CRIADOS NA SIDEBAR ---
        log_placeholder = st.empty()

        if btn_extrair:
            # Reseta os logs e a lista de arquivos criados
            st.session_state.log_messages = []
            st.session_state.arquivos_criados = []

            ano_para_extrair = int(st.session_state.ano_input)
            mes_para_extrair = st.session_state.mes_input
            
            # Marca o timestamp de início para sabermos quais arquivos foram criados NESTA rodada
            inicio_extracao = time.time()
            
            # Função de callback chamada pelo pipeline
            def stream_log(msg):
                st.session_state.log_messages.append(msg)
                
                # Monitora a pasta 'data' em busca de novos arquivos parquet criados após o início_extracao
                arquivos_atuais = []
                if os.path.exists('data'):
                    for f in glob.glob(os.path.join('data', '*.parquet')):
                        # Se o arquivo foi modificado/criado após o início da extração
                        if os.path.getmtime(f) >= inicio_extracao:
                            nome_arq = os.path.basename(f)
                            if nome_arq not in arquivos_atuais:
                                arquivos_atuais.append(nome_arq)
                
                st.session_state.arquivos_criados = sorted(arquivos_atuais)

                # Atualiza a interface gráfica em tempo real
                with log_placeholder.container():
                    st.caption("🪵 Logs de Extração (Tempo Real)")
                    st.code("\n".join(st.session_state.log_messages[-50:]), language="text")
                    
                    if st.session_state.arquivos_criados:
                        st.caption("📁 Arquivos criados no disco:")
                        for arq in st.session_state.arquivos_criados:
                            st.markdown(f"🔹 `{arq}`")

            municipio_selecionado = None if st.session_state.mun_input == "Todos" else opcoes_mun[st.session_state.mun_input]
            
            with st.spinner("Buscando dados no TCE..."):
                try:
                    executar_pipeline(
                        ano_para_extrair, 
                        mes_selecionado=mes_para_extrair, 
                        municipio_selecionado=municipio_selecionado, 
                        log_func=stream_log
                    )
                    st.success("Extração concluída com sucesso!")
                except Exception as e:
                    st.error(f"Erro durante a extração: {e}")
        
        # Mantém visível os logs e arquivos da última extração se o usuário navegar pelo app
        elif st.session_state.log_messages:
            with log_placeholder.container():
                # Mostra os arquivos que foram criados na última rodada
                if st.session_state.arquivos_criados:
                    st.subheader("📁 Últimos Arquivos Salvos")
                    for arq in st.session_state.arquivos_criados:
                        st.markdown(f"✅ `{arq}`")
                    st.divider()

                with st.expander("🪵 Ver Histórico de Logs", expanded=False):
                    st.code("\n".join(st.session_state.log_messages), language="text")
                    if st.button("Limpar Logs e Histórico", key="clear_logs"):
                        st.session_state.log_messages = []
                        st.session_state.arquivos_criados = []
                        st.rerun()

    # --- ÁREA PRINCIPAL ---
    st.header("Visualizar Dados")

    def carregar_e_exibir_dados(tipo_arquivo_prefixo):
        ano = st.session_state.ano_input
        mes = st.session_state.mes_input
        mun = st.session_state.mun_input

        # Configurar os curingas para a busca
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
            
            # Chaves únicas para os seletores
            key_select = f"select_{tipo_arquivo_prefixo}_{ano}"
            key_df_cache = f"df_{tipo_arquivo_prefixo}"
            key_file_cache = f"file_{tipo_arquivo_prefixo}"
            key_page = f"page_{tipo_arquivo_prefixo}"

            arquivo_selecionado_nome = st.selectbox(
                f"Selecione o arquivo de {tipo_arquivo_prefixo}:",
                options=nomes_arquivos,
                key=key_select
            )

            caminho_completo = os.path.join('data', arquivo_selecionado_nome)

            # Botão para disparar a leitura do arquivo físico
            if st.button(f"📄 Abrir {arquivo_selecionado_nome}", key=f"btn_view_{tipo_arquivo_prefixo}"):
                try:
                    # Carrega o arquivo e reseta para a página 1 no session state
                    st.session_state[key_df_cache] = pd.read_parquet(caminho_completo)
                    st.session_state[key_file_cache] = arquivo_selecionado_nome
                    st.session_state[key_page] = 1
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo: {e}")

            # Se o arquivo já estiver na memória, renderiza a tabela e a paginação
            if key_df_cache in st.session_state and st.session_state[key_file_cache] == arquivo_selecionado_nome:
                df = st.session_state[key_df_cache]
                total_registros = len(df)
                itens_por_pagina = 500

                # Cálculo de Páginas
                total_paginas = max(1, (total_registros + itens_por_pagina - 1) // itens_por_pagina)

                # Inicializa ou valida a página atual no session state
                if key_page not in st.session_state:
                    st.session_state[key_page] = 1

                st.divider()
                st.subheader(f"Visualizando: {arquivo_selecionado_nome}")
                st.caption(f"Total de registros na base: {total_registros:,}")

                # --- CONTROLADORES DE PAGINAÇÃO ---
                col_pag1, col_pag2, col_pag3 = st.columns([1, 2, 1])

                with col_pag1:
                    btn_anterior = st.button(
                        "⬅️ Anterior", 
                        key=f"prev_{tipo_arquivo_prefixo}", 
                        disabled=(st.session_state[key_page] <= 1),
                        use_container_width=True
                    )
                    if btn_anterior:
                        st.session_state[key_page] -= 1
                        st.rerun()

                with col_pag2:
                    st.markdown(
                        f"<p style='text-align: center; font-weight: bold; margin-top: 8px;'>"
                        f"Página {st.session_state[key_page]} de {total_paginas}"
                        f"</p>", 
                        unsafe_allow_html=True
                    )

                with col_pag3:
                    btn_proximo = st.button(
                        "Próximo ➡️", 
                        key=f"next_{tipo_arquivo_prefixo}", 
                        disabled=(st.session_state[key_page] >= total_paginas),
                        use_container_width=True
                    )
                    if btn_proximo:
                        st.session_state[key_page] += 1
                        st.rerun()

                # --- FATIAMENTO (SLICING) DO DATAFRAME ---
                inicio = (st.session_state[key_page] - 1) * itens_por_pagina
                fim = min(inicio + itens_por_pagina, total_registros)
                df_fatiado = df.iloc[inicio:fim]

                # Exibe o intervalo que está sendo visualizado
                st.info(f"Mostrando registros de {inicio + 1:,} até {fim:,} (Total: {total_registros:,})")
                
                # Renderiza o DataFrame
                st.dataframe(df_fatiado, use_container_width=True)

                # Botão de Download completo do arquivo original
                st.download_button(
                    label="📥 Baixar este arquivo completo (CSV)",
                    data=df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig'),
                    file_name=arquivo_selecionado_nome.replace('.parquet', '.csv'),
                    mime='text/csv',
                    use_container_width=True
                )
        else:
            st.warning(f"Nenhum arquivo de `{tipo_arquivo_prefixo}` encontrado para o ano {ano_str}.")
            st.info("Ajuste o 'Ano Base' na barra lateral.")

    # Criação dinâmica das abas
    abas = st.tabs(list(DATA_MAP.keys()))
    
    for i, name_tab in enumerate(DATA_MAP.keys()):
        with abas[i]:
            carregar_e_exibir_dados(DATA_MAP[name_tab])