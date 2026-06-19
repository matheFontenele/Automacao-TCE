import os
import glob
import json
import pandas as pd
import streamlit as st

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA_TCE = os.path.join(ROOT_DIR, 'data')
PASTA_INTERNAL = os.path.join(ROOT_DIR, 'data_internal')


# ==========================================
# FUNÇÕES DE APOIO E LÓGICA (COMPARTILHADAS)
# ==========================================

@st.cache_data(show_spinner=False)
def converter_df_para_csv(df):
    """Cache da conversão de DataFrame para CSV para evitar travamentos."""
    if df is None or df.empty:
        return b""
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

def padronizar_chave(serie):
    """Limpa as chaves para garantir o match exato entre JSON e TCE."""
    s = serie.astype(str)
    s = s.str.replace(r'\D', '', regex=True)
    s = s.str.replace(r'^\d+?0{4,}', '', regex=True)
    s = s.str.lstrip('0')
    return s.replace('', '0')

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
# 🧩 BLOCO 2: NOVA LÓGICA (ESQUELETO)
# ==========================================

def render_bloco_nova_logica():
    """
    Espaço reservado para a nova lógica de comparação.
    Aqui você pode implementar cruzamentos diferentes, como:
    - Empenhos vs Pagamentos internos
    - Conciliação Bancária
    - Validação de Contratos
    """
    st.markdown("#### 🆕 Nova Lógica de Comparação")
    st.caption("Espaço reservado para implementação do novo fluxo de validação.")
    
    st.info("🚧 **Em desenvolvimento** — Selecione os parâmetros da nova lógica abaixo:")
    
    # Exemplo de estrutura para a nova lógica
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Parâmetro A (Ex: Nº Contrato)", key="param_a")
    with col2:
        st.text_input("Parâmetro B (Ex: CNPJ Fornecedor)", key="param_b")
    
    st.file_uploader("Upload de arquivo de referência:", type=['csv', 'xlsx', 'json'], key="upload_nova_logica")
    
    if st.button("🔍 Executar Nova Análise", key="btn_nova_logica"):
        st.warning("Lógica ainda não implementada. Adicione o código de processamento aqui.")


# ==========================================
# 🎛️ ORQUESTRADOR PRINCIPAL (RENDERIZAÇÃO DA PÁGINA)
# ==========================================

def render_aba_comparacao():
    """Página principal que permite alternar entre os dois blocos lógicos."""
    st.header("⚖️ Central de Comparação e Validação de Dados")
    
    # Seletor principal de modo
    modo_selecionado = st.radio(
        "Escolha o tipo de comparação que deseja realizar:",
        options=["🏛️ Comparação Patrimonial", "🆕 Nova Lógica"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Roteamento para o bloco correspondente
    if modo_selecionado == "🏛️ Comparação Patrimonial":
        render_bloco_patrimonial()
    else:
        render_bloco_nova_logica()