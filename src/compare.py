import os
import glob
import json
import io
import pandas as pd
import streamlit as st

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_TCE = os.path.join(ROOT_DIR, 'data')
PASTA_INTERNAL = os.path.join(ROOT_DIR, 'data_internal')


# ==========================================
# FUNÇÕES DE APOIO E LÓGICA (COMPARTILHADAS)
# ==========================================

@st.cache_data(show_spinner=False)
def converter_df_para_xlsx(df):
    """Cache da conversão de DataFrame para XLSX."""
    if df is None or df.empty:
        return b""
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Cruzamento')
    return output.getvalue()

def converter_df_para_csv(df):
    """Cache da conversão de DataFrame para CSV para evitar travamentos."""
    if df is None or df.empty:
        return b""
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

def padronizar_chave(serie):
    s = serie.astype(str).str.replace(r'[^0-9]', '', regex=True)
    s = s.str.lstrip('0')
    return s.where(s != '', '0')


def ler_txt_upload(arquivo_upload, delimitador=',', encoding='utf-8', tem_cabecalho=True):
    """
    Lê um arquivo TXT/CSV enviado pelo usuário com configuração flexível.
    Retorna um DataFrame ou None em caso de erro.
    """
    if arquivo_upload is None:
        return None
    
    bytes_data = arquivo_upload.getvalue()
    
    # Tenta ler com o encoding escolhido, fallback para latin-1
    for enc in [encoding, 'latin-1', 'cp1252', 'utf-8']:
        try:
            if tem_cabecalho:
                # Lê com cabeçalho na primeira linha
                df = pd.read_csv(
                    io.BytesIO(bytes_data),
                    sep=delimitador,
                    encoding=enc,
                    dtype=str,
                    on_bad_lines='skip'
                )
            else:
                # Lê sem cabeçalho - gera nomes automáticos
                df = pd.read_csv(
                    io.BytesIO(bytes_data),
                    sep=delimitador,
                    encoding=enc,
                    dtype=str,
                    on_bad_lines='skip',
                    header=None
                )
                # Gera nomes de colunas genéricos
                df.columns = [f'col_{i+1}' for i in df.columns]
            
            return df
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
    
    return None


# ==========================================
# 🧩 BLOCO 1: COMPARAÇÃO PATRIMONIAL (LÓGICA ATUAL)
# ==========================================

def carregar_dados_patrimonio(caminho_json: str, caminhos_parquet: list) -> tuple:
    """Carrega o JSON interno e os Parquets do TCE para bens patrimoniais."""
    with open(caminho_json, 'r', encoding='utf-8') as f:
        json_bruto = json.load(f)
    chave_sql = list(json_bruto.keys())[0]
    df_interno = pd.DataFrame(json_bruto[chave_sql])
    
    dfs_tce = [pd.read_parquet(c) for c in caminhos_parquet]
    df_tce_completo = pd.concat(dfs_tce, ignore_index=True)
    
    return df_interno, df_tce_completo

def processar_mesclagem_patrimonio(df_interno, df_tce_completo) -> pd.DataFrame:
    """Realiza o cruzamento entre base interna (TOMBO) e TCE (numero_registro)."""
    df_interno['chave_join'] = padronizar_chave(df_interno['TOMBO'])
    df_tce_completo['chave_join'] = padronizar_chave(df_tce_completo['numero_registro'])

    df_mesclado = pd.merge(
        df_interno, 
        df_tce_completo, 
        on='chave_join', 
        how='outer', 
        suffixes=('_interno', '_tce')
    )
    
    for col in ['PAT_ID', 'patrimonio_id', 'UOE_ID']:
        if col in df_mesclado.columns:
            df_mesclado[col] = pd.to_numeric(df_mesclado[col], errors='coerce').astype('Int64')
            
    return df_mesclado

def exibir_resultados_patrimonio(df_interno, df_tce_completo, df_full):
    """Renderiza métricas, abas e botões de download para a comparação patrimonial."""
    df_sucesso = df_full[df_full['TOMBO'].notna() & df_full['numero_registro'].notna()]
    df_so_json = df_full[df_full['numero_registro'].isna()]
    df_so_tce = df_full[df_full['TOMBO'].isna()]

    st.divider()
    st.markdown("### 🎯 Resultado da Mesclagem Patrimonial")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("JSON Interno", f"{len(df_interno):,}".replace(",", "."))
    c2.metric("TCE-CE", f"{len(df_tce_completo):,}".replace(",", "."))
    c3.metric("✅ Cruzados", f"{len(df_sucesso):,}".replace(",", "."))
    c4.metric("Total Linhas", f"{len(df_full):,}".replace(",", "."))

    tabs = st.tabs(["🌐 Completo", "✅ Sucesso", "⚠️ Faltam no TCE", "⚠️ Faltam na base interna"])
    dados = [df_full, df_sucesso, df_so_json, df_so_tce]
    nomes = ["patrimonio_completo.csv", "patrimonio_sucesso.csv", "patrimonio_faltantes.csv", "patrimonio_sobras.csv"]

    for i, tab in enumerate(tabs):
        with tab:
            st.write(f"Visualizando amostra (500 de **{len(dados[i]):,}** linhas encontradas):")
            st.dataframe(dados[i].head(500), use_container_width=True, hide_index=True)
            st.download_button(
                label=f"📥 Baixar CSV ({len(dados[i]):,} linhas)",
                data=converter_df_para_csv(dados[i]),
                file_name=nomes[i],
                mime="text/csv",
                key=f"btn_download_patrimonio_{i}"
            )

def render_bloco_patrimonial():
    """Interface completa para a comparação de bens patrimoniais."""
    st.markdown("#### 🏛️ Comparação Patrimonial")
    st.caption("Cruza o TOMBO da base interna com o `numero_registro` do TCE-CE.")
    
    PASTA_INTERNAL, PASTA_TCE = 'data_internal', 'data'
    os.makedirs(PASTA_INTERNAL, exist_ok=True)

    st.markdown("**📥 1. Dados Internos (JSON)**")
    
    caminho_json_salvo = None
    arquivos_json = sorted([f for f in os.listdir(PASTA_INTERNAL) if f.endswith('.json')])
    
    metodo_origem = st.radio(
        "Como deseja importar os dados?",
        options=["Selecionar arquivo existente", "Fazer novo upload"],
        horizontal=True,
        key="metodo_origem_patrimonio"
    )

    if metodo_origem == "Selecionar arquivo existente":
        if arquivos_json:
            sel = st.selectbox("Selecione o arquivo JSON:", arquivos_json, key="sel_json_patrimonio")
            caminho_json_salvo = os.path.join(PASTA_INTERNAL, sel)
        else:
            st.warning("Nenhum arquivo JSON encontrado na pasta data_internal.")
    else:
        arquivo_upload = st.file_uploader("Upload de arquivo JSON:", type=['json'], key="upload_patrimonio")
        if arquivo_upload:
            caminho_json_salvo = os.path.join(PASTA_INTERNAL, arquivo_upload.name)
            with open(caminho_json_salvo, "wb") as f:
                f.write(arquivo_upload.getbuffer())
            st.success(f"✅ Arquivo {arquivo_upload.name} salvo com sucesso!")
            st.rerun()

    st.markdown("**📄 2. Bases do TCE-CE (Bens Incorporados)**")
    prefixo = "bens_incorporados_patrimonio_municipio"
    arquivos_tce = sorted(glob.glob(os.path.join(PASTA_TCE, f"{prefixo}_*.parquet")))
    selecionados = st.multiselect(
        "Selecione os arquivos:", 
        [os.path.basename(f) for f in arquivos_tce],
        key="multiselect_patrimonio"
    )

    if caminho_json_salvo and selecionados:
        if st.button("🚀 Processar Cruzamento Patrimonial", type="primary", key="btn_processar_patrimonio"):
            with st.spinner("Extraindo e processando informações em memória..."):
                caminhos = [os.path.join(PASTA_TCE, arq) for arq in selecionados]
                df_int, df_tce = carregar_dados_patrimonio(caminho_json_salvo, caminhos)
                df_full = processar_mesclagem_patrimonio(df_int, df_tce)
                exibir_resultados_patrimonio(df_int, df_tce, df_full)
    else:
        st.info("👈 Selecione o JSON e as bases do TCE para iniciar.")


# ==========================================
# 🧩 BLOCO 2: CRUZAMENTO TXT × PARQUET (NOVA LÓGICA)
# ==========================================

def processar_cruzamento_txt_parquet(df_txt, df_parquet, coluna_txt, coluna_parquet, normalizar=True):
    """Versão otimizada sem cópias desnecessárias."""
    # Renomeia colunas SEM copiar o DataFrame
    df_a = df_txt.rename(columns={c: f'TXT_{c}' for c in df_txt.columns})
    df_b = df_parquet.rename(columns={c: f'TCE_{c}' for c in df_parquet.columns})
    
    chave_txt = f'TXT_{coluna_txt}'
    chave_parquet = f'TCE_{coluna_parquet}'
    
    # Aplica normalização apenas nas colunas de chave (não no DF todo)
    if normalizar:
        df_a['__chave__'] = padronizar_chave(df_a[chave_txt])
        df_b['__chave__'] = padronizar_chave(df_b[chave_parquet])
    else:
        df_a['__chave__'] = df_a[chave_txt].astype(str).str.strip()
        df_b['__chave__'] = df_b[chave_parquet].astype(str).str.strip()
    
    # Inner join
    df_mesclado = pd.merge(
        df_a, df_b,
        on='__chave__',
        how='inner'
    )
    
    # Remove coluna auxiliar
    if '__chave__' in df_mesclado.columns:
        df_mesclado = df_mesclado.drop(columns=['__chave__'])
    
    return df_mesclado


def render_bloco_txt_parquet():
    """
    Interface para cruzar um arquivo TXT/CSV do usuário
    com os parquets de bens incorporados.
    """
    st.markdown("#### 🔗 Cruzamento TXT × Parquet")
    st.caption(
        "Faça upload de um arquivo TXT/CSV e cruze com os parquets de bens incorporados. "
        "Será gerada uma lista **apenas com os registros que casam**, mesclando as informações de ambos."
    )
    
    if os.path.exists(PASTA_TCE):
        todos_arquivos = os.listdir(PASTA_TCE)
        parquets = [f for f in todos_arquivos if f.endswith('.parquet')]
        
        st.success(f"✅ Pasta existe! Encontrados **{len(parquets)}** arquivos parquet")
        
        # Filtra especificamente por bens_incorporados
        prefixo = "bens_incorporados_patrimonio_municipio"
        bens_parquets = sorted([f for f in parquets if prefixo in f.lower()])
        
        if bens_parquets:
            st.info(f"📊 **{len(bens_parquets)}** arquivos de bens incorporados disponíveis")
            
            # Mostra os primeiros
            with st.expander("📋 Ver todos os arquivos de bens", expanded=False):
                for i, p in enumerate(bens_parquets, 1):
                    st.caption(f"{i}. {p}")
        else:
            st.warning(f"⚠️ Nenhum arquivo com '{prefixo}' encontrado")
            st.caption("📋 Arquivos disponíveis:")
            for p in sorted(parquets)[:5]:
                st.caption(f"• {p}")
    else:
        st.error(f"❌ Pasta não existe!")
        return
    
    st.divider()
    
    # ========================================
    # 1. UPLOAD DO ARQUIVO TXT
    # ========================================
        # ========================================
    # 1. UPLOAD DO ARQUIVO TXT
    # ========================================
    st.markdown("**📥 1. Seu Arquivo (TXT/CSV)**")
    
    col_delim, col_enc = st.columns(2)
    with col_delim:
        opcoes_delim = {
            "Vírgula (,)": ",",
            "Ponto-e-vírgula (;)": ";",
            "Tab (\\t)": "\t",
            "Pipe (|)": "|",
        }
        delimitador_label = st.selectbox(
            "Delimitador do arquivo:",
            options=list(opcoes_delim.keys()),
            key="delim_txt"
        )
        delimitador = opcoes_delim[delimitador_label]
    with col_enc:
        encoding = st.selectbox(
            "Encoding:",
            options=["utf-8", "latin-1", "cp1252"],
            index=1,
            key="enc_txt"
        )
    
    # Nova opção: tem cabeçalho?
    tem_cabecalho = True
    
    upload_txt = st.file_uploader(
        "Upload do arquivo TXT/CSV:",
        type=['txt', 'csv', 'pat', 'dat', 'log'],
        key="upload_txt"
    )
    
    df_txt = None
    if upload_txt is not None:
        df_txt = ler_txt_upload(upload_txt, delimitador, encoding, tem_cabecalho)
        
        if df_txt is None or df_txt.empty:
            st.error("❌ Não foi possível ler o arquivo.")
        else:
            st.success(f"✅ Carregado: **{len(df_txt):,}** linhas × **{len(df_txt.columns)}** colunas")
            with st.expander("👁️ Pré-visualizar arquivo TXT", expanded=False):
                st.dataframe(df_txt.head(10), use_container_width=True, hide_index=True)
                st.caption("**Colunas detectadas:** " + ", ".join(df_txt.columns.tolist()))
    
    # ========================================
    # 2. SELEÇÃO DOS PARQUETS
    # ========================================
    st.markdown("**📄 2. Bases do TCE-CE**")
    
    if bens_parquets:
        selecionados = st.multiselect(
            "Selecione os arquivos parquet:",
            options=bens_parquets,
            default=bens_parquets,  # Seleciona todos por padrão
            key="multiselect_txt"
        )
    else:
        selecionados = st.multiselect(
            "Selecione os arquivos parquet:",
            options=parquets,
            key="multiselect_txt"
        )
    
    # ========================================
    # 3. CONFIGURAÇÃO E PROCESSAMENTO
    # ========================================
    if df_txt is not None and selecionados:
        st.divider()
        st.markdown("**⚙️ Configuração do Cruzamento**")
        
        col_a, col_b = st.columns(2)
        with col_a:
            coluna_txt = st.selectbox(
                "Coluna do SEU arquivo (chave):",
                options=df_txt.columns.tolist(),
                key="col_txt"
            )
        with col_b:
            # Lê o primeiro parquet para pegar colunas
            try:
                df_preview = pd.read_parquet(os.path.join(PASTA_TCE, selecionados[0]))
                colunas_parquet = df_preview.columns.tolist()
                
                # Sugere numero_registro se existir
                index_default = colunas_parquet.index('numero_registro') if 'numero_registro' in colunas_parquet else 0
            except Exception as e:
                st.error(f"Erro ao ler parquet: {e}")
                colunas_parquet = []
                index_default = 0
            
            coluna_parquet = st.selectbox(
                "Coluna do Parquet (chave):",
                options=colunas_parquet,
                index=index_default,
                key="col_parquet"
            )
        
        if st.button("🚀 Processar Cruzamento", type="primary", key="btn_processar_txt"):
            with st.spinner("Processando..."):
                try:
                    # Carrega todos os parquets selecionados
                    dfs_parquet = []
                    for arq in selecionados:
                        caminho = os.path.join(PASTA_TCE, arq)
                        dfs_parquet.append(pd.read_parquet(caminho))
                    
                    df_parquet_completo = pd.concat(dfs_parquet, ignore_index=True)
                    
                    st.info(f"📊 **{len(df_parquet_completo):,}** registros dos parquets")
                    
                    # Processa o cruzamento
                    df_mesclado = processar_cruzamento_txt_parquet(
                        df_txt, df_parquet_completo,
                        coluna_txt, coluna_parquet,
                        normalizar=True
                    )
                    
                    # ========================================
                    # RESULTADOS
                    # ========================================
                    st.divider()
                    st.markdown("### 🎯 Resultado")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("TXT", f"{len(df_txt):,}")
                    c2.metric("Parquet", f"{len(df_parquet_completo):,}")
                    c3.metric("✅ Casados", f"{len(df_mesclado):,}")
                    
                    if df_mesclado.empty:
                        st.warning("⚠️ Nenhum registro casou.")
                    else:
                        st.success(f"✅ **{len(df_mesclado):,}** registros mesclados!")
                        
                        max_preview = st.slider("Linhas para pré-visualizar:", 100, 2000, 200, step=100)
                        st.dataframe(df_mesclado.head(max_preview), use_container_width=True, hide_index=True)
                        
                        st.download_button(
                            label=f"📥 Baixar Excel ({len(df_mesclado):,} linhas)",
                            data=converter_df_para_xlsx(df_mesclado),
                            file_name="cruzamento_txt_parquet.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="btn_download_txt"
                        )
                        
                except Exception as e:
                    st.error(f"❌ Erro: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    else:
        st.info("👈 Upload do TXT e selecione parquets para iniciar.")


# ==========================================
# 🎛️ ORQUESTRADOR PRINCIPAL (RENDERIZAÇÃO DA PÁGINA)
# ==========================================

def render_aba_comparacao():
    """Página principal que permite alternar entre os três blocos lógicos."""
    st.header("⚖️ Central de Comparação e Validação de Dados")
    
    # Seletor principal de modo (agora com 3 opções)
    modo_selecionado = st.radio(
        "Escolha o tipo de comparação que deseja realizar:",
        options=[
            "🏛️ Comparação Patrimonial",
            "🔗 Cruzamento TXT × Parquet"
        ],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Roteamento para o bloco correspondente
    if modo_selecionado == "🏛️ Comparação Patrimonial":
        render_bloco_patrimonial()
    elif modo_selecionado == "🔗 Cruzamento TXT × Parquet":
        render_bloco_txt_parquet()