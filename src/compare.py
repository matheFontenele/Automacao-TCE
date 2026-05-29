import os
import glob
import json
import pandas as pd
import streamlit as st

# ==========================================
# FUNÇÕES DE APOIO E LÓGICA
# ==========================================

@st.cache_data(show_spinner=False)
def converter_df_para_csv(df):
    """Cache da conversão de DataFrame para CSV para evitar travamentos."""
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

def padronizar_chave(serie):
    """Limpa as chaves para garantir o match exato entre JSON e TCE."""
    s = serie.astype(str)
    
    # 1. Remove qualquer coisa que não seja dígito (letras, hífens, etc)
    s = s.str.replace(r'\D', '', regex=True)
    
    # 2. Remove o padrão de preenchimento do TCE
    s = s.str.replace(r'^\d+?0{4,}', '', regex=True)
    
    # 3. Remove os zeros à esquerda normais que possam ter sobrado
    s = s.str.lstrip('0')
    
    # 4. Retorna '0' se a string ficar vazia
    return s.replace('', '0')

# ==========================================
# 1. FUNÇÃO DE EXTRAÇÃO (CARREGAMENTO)
# ==========================================
def carregar_dados(caminho_json: str, caminhos_parquet: list) -> tuple:
    # Lê o JSON interno
    with open(caminho_json, 'r', encoding='utf-8') as f:
        json_bruto = json.load(f)
    chave_sql = list(json_bruto.keys())[0]
    df_interno = pd.DataFrame(json_bruto[chave_sql])
    
    # Lê e concatena os Parquets do TCE
    dfs_tce = [pd.read_parquet(c) for c in caminhos_parquet]
    df_tce_completo = pd.concat(dfs_tce, ignore_index=True)
    
    return df_interno, df_tce_completo

# ==========================================
# 2. FUNÇÃO DE MESCLAGEM (PROCESSAMENTO)
# ==========================================
def processar_mesclagem(df_interno, df_tce_completo) -> pd.DataFrame:
    # Aplica a limpeza inteligente nas chaves
    df_interno['chave_join'] = padronizar_chave(df_interno['TOMBO'])
    df_tce_completo['chave_join'] = padronizar_chave(df_tce_completo['numero_registro'])

    # Faz o cruzamento (Full Outer Join)
    df_mesclado = pd.merge(df_interno, df_tce_completo, on='chave_join', how='outer', suffixes=('_interno', '_tce'))
    
    # Garante que IDs do JSON aceitem nulos sem virar float (.0)
    for col in ['PAT_ID', 'patrimonio_id', 'UOE_ID']:
        if col in df_mesclado.columns:
            df_mesclado[col] = pd.to_numeric(df_mesclado[col], errors='coerce').astype('Int64')
            
    return df_mesclado

# ==========================================
# 3. FUNÇÃO DE EXIBIÇÃO (INTERFACE / VISUAL)
# ==========================================
def exibir_resultados(df_interno, df_tce_completo, df_full):
    # Fatiamento dos cenários
    df_sucesso = df_full[df_full['TOMBO'].notna() & df_full['numero_registro'].notna()]
    df_so_json = df_full[df_full['numero_registro'].isna()]
    df_so_tce = df_full[df_full['TOMBO'].isna()]

    st.divider()
    st.markdown("### 🎯 Resultado da Mesclagem")

    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("JSON", f"{len(df_interno):,}".replace(",", "."))
    c2.metric("TCE", f"{len(df_tce_completo):,}".replace(",", "."))
    c3.metric("✅ Sucesso", f"{len(df_sucesso):,}".replace(",", "."))
    c4.metric("Total", f"{len(df_full):,}".replace(",", "."))

    # Abas com exibição otimizada
    tabs = st.tabs(["🌐 Completo", "✅ Sucesso", "⚠️ Faltam no TCE", "⚠️ Faltam na base interna"])
    dados = [df_full, df_sucesso, df_so_json, df_so_tce]
    nomes = ["completo.csv", "sucesso.csv", "faltantes.csv", "sobras.csv"]

    for i, tab in enumerate(tabs):
        with tab:
            st.write(f"Visualizando amostra (500 de **{len(dados[i]):,}** linhas encontradas):")
            st.dataframe(dados[i].head(500), use_container_width=True, hide_index=True)
            st.download_button(
                label=f"📥 Baixar CSV Completo ({len(dados[i]):,} linhas)",
                data=converter_df_para_csv(dados[i]),
                file_name=nomes[i],
                mime="text/csv",
                key=f"btn_download_{i}"
            )

# ==========================================
# FUNÇÃO PRINCIPAL (RENDERIZAÇÃO DA PÁGINA)
# ==========================================
def render_aba_comparacao():
    st.header("⚖️ Comparação e Validação de Dados")
    PASTA_INTERNAL, PASTA_TCE = 'data_internal', 'data'
    os.makedirs(PASTA_INTERNAL, exist_ok=True)

    st.subheader("📥 1. Obter Dados Internos (JSON)")
    
    caminho_json_salvo = None
    arquivos_json = sorted([f for f in os.listdir(PASTA_INTERNAL) if f.endswith('.json')])
    
    metodo_origem = st.radio(
        "Como deseja importar os dados?",
        options=["Selecionar arquivo existente", "Fazer novo upload"],
        horizontal=True,
        key="metodo_origem"
    )

    if metodo_origem == "Selecionar arquivo existente":
        if arquivos_json:
            sel = st.selectbox("Selecione o arquivo JSON:", arquivos_json)
            caminho_json_salvo = os.path.join(PASTA_INTERNAL, sel)
        else:
            st.warning("Nenhum arquivo JSON encontrado na pasta data_internal.")
    else:
        arquivo_upload = st.file_uploader("Upload de arquivo JSON:", type=['json'])
        if arquivo_upload:
            caminho_json_salvo = os.path.join(PASTA_INTERNAL, arquivo_upload.name)
            with open(caminho_json_salvo, "wb") as f:
                f.write(arquivo_upload.getbuffer())
            st.success(f"✅ Arquivo {arquivo_upload.name} salvo com sucesso!")
            st.rerun()

    st.subheader("📄 2. Selecionar Bases do TCE-CE")
    prefixo = "bens_incorporados_patrimonio_municipio"
    arquivos_tce = sorted(glob.glob(os.path.join(PASTA_TCE, f"{prefixo}_*.parquet")))
    selecionados = st.multiselect("Bases do TCE:", [os.path.basename(f) for f in arquivos_tce])

    # O botão atua apenas como gatilho (Orquestrador)
    if caminho_json_salvo and selecionados:
        if st.button("🚀 Processar e Cruzar Dados", type="primary"):
            with st.spinner("Extraindo e processando informações em memória..."):
                caminhos = [os.path.join(PASTA_TCE, arq) for arq in selecionados]
                
                # 1. Extração
                df_int, df_tce = carregar_dados(caminho_json_salvo, caminhos)
                
                # 2. Mesclagem
                df_full = processar_mesclagem(df_int, df_tce)
                
                # 3. Exibição
                exibir_resultados(df_int, df_tce, df_full)
    else:
        st.info("👈 Por favor, selecione ou envie o arquivo JSON e escolha as bases do TCE para iniciar.")