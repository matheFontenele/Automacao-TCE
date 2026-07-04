import streamlit as st
import pandas as pd
import glob
import os
import re
import json
from PIL import Image

@st.cache_data
def carregar_mapa_municipios():
    caminho = 'municipios.json'
    if not os.path.exists(caminho):
        caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'municipios.json')
        
    mapa = {}
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            for m in dados.get('elements', []):
                cod = m['codigo_municipio']
                nome = m['nome_municipio']
                mapa[cod] = f"{nome} ({cod})"
    except Exception as e:
        st.error(f"Erro ao carregar mapa de municípios: {e}")
        
    return mapa

@st.cache_data
def carregar_empenhos_reais():
    """
    Lê os arquivos Parquet de forma otimizada utilizando projeção colunar.
    Isso reduz drasticamente o uso de memória e o tempo de carregamento.
    """
    caminho_base = "data/"
    if not os.path.exists(caminho_base):
        caminho_base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        
    arquivos = glob.glob(os.path.join(caminho_base, "notas_empenho_*.parquet"))
    
    if not arquivos:
        return pd.DataFrame()
        
    colunas_alvo = [
        'numero_empenho', 
        'nome_negociante', 
        'numero_documento_negociante', 
        'codigo_municipio', 
        'valor_empenhado'
    ]
    
    lista_dfs = []
    
    for f in arquivos:
        try:
            df_temp = pd.read_parquet(f, columns=colunas_alvo)
            df_temp = df_temp.dropna(subset=['numero_empenho', 'numero_documento_negociante'])
            lista_dfs.append(df_temp)
        except Exception:
            continue 
            
    if not lista_dfs:
        return pd.DataFrame()
        
    df = pd.concat(lista_dfs, ignore_index=True)
    df = df.drop_duplicates(subset=['numero_empenho'])
    
    return df

def limpar_apenas_numeros(texto):
    """Remove pontos, barras e traços de CNPJs para garantir o match perfeito."""
    if pd.isna(texto) or not texto:
        return ""
    return re.sub(r'[^0-9]', '', str(texto))

def render_audit_page():
    st.header("🔎 Auditoria Antifraude - Visão Computacional")
    st.markdown("Reconciliação automática entre Notas Fiscais físicas e a base de dados oficial do TCE-CE.")

    # 1. CARREGAMENTO DOS DADOS REAIS E MAPA
    df_empenhos = carregar_empenhos_reais()
    mapa_municipios = carregar_mapa_municipios()

    if df_empenhos.empty:
        st.warning("⚠️ Nenhum dado de empenho encontrado. Vá na aba de Extração e baixe os dados do TCE primeiro.")
        return

    st.subheader("1. Selecione o Contrato (Base TCE-CE)")
    
    # ==========================================
    # FILTROS EM CASCATA (AGORA COM NOMES REAIS)
    # ==========================================
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        if 'codigo_municipio' in df_empenhos.columns:
            # Pega só os códigos que realmente existem nos parquets baixados
            codigos_baixados = df_empenhos['codigo_municipio'].dropna().unique().tolist()
            
            # Traduz os códigos para os nomes usando nosso dicionário
            opcoes_muns = ["Todos"] + sorted([mapa_municipios.get(cod, f"Desconhecido ({cod})") for cod in codigos_baixados])
            
            mun_selecionado = st.selectbox("📍 Filtrar por Município", opcoes_muns)
            
            # Se não for "Todos", isola o código de novo extraindo de dentro dos parênteses
            if mun_selecionado != "Todos":
                mun_filtro = mun_selecionado.split('(')[-1].replace(')', '').strip()
            else:
                mun_filtro = "Todos"
        else:
            mun_filtro = "Todos"
            
    with col_filtro2:
        busca_fornecedor = st.text_input("🏢 Buscar Fornecedor (Nome ou CNPJ)", placeholder="Ex: CONSTRUTORA ou 123456")

    # Aplicando a "Lâmina" do Pandas
    df_filtrado = df_empenhos.copy()
    
    if mun_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado['codigo_municipio'] == mun_filtro]
        
    if busca_fornecedor:
        termo_busca = busca_fornecedor.lower()
        df_filtrado = df_filtrado[
            df_filtrado['nome_negociante'].astype(str).str.lower().str.contains(termo_busca, na=False) |
            df_filtrado['numero_documento_negociante'].astype(str).str.lower().str.contains(termo_busca, na=False)
        ]

    # ==========================================
    # SELEÇÃO FINAL E EXIBIÇÃO
    # ==========================================
    if df_filtrado.empty:
        st.warning("Nenhum contrato encontrado com os filtros aplicados. Tente limpar a busca.")
        return 
        
    opcoes_display = df_filtrado['numero_empenho'].astype(str) + " — " + df_filtrado['nome_negociante'].astype(str)
    empenho_selecionado = st.selectbox("Selecione o Empenho Alvo", opcoes_display)
    
    numero_alvo = empenho_selecionado.split(" — ")[0]
    linha_alvo = df_filtrado[df_filtrado['numero_empenho'].astype(str) == numero_alvo].iloc[0]

    cnpj_esperado = str(linha_alvo['numero_documento_negociante'])
    valor_esperado = pd.to_numeric(linha_alvo['valor_empenhado'], errors='coerce')
    
    # Exibe também o nome amigável do município na caixa azul de informação
    nome_mun_info = mapa_municipios.get(str(linha_alvo['codigo_municipio']), str(linha_alvo['codigo_municipio']))
    
    st.info(f"**📍 Órgão:** {nome_mun_info} | **📄 Empenho:** {linha_alvo['numero_empenho']} | **🏢 Fornecedor:** {cnpj_esperado} | **💰 Valor Empenhado:** R$ {valor_esperado:,.2f}")

    # ==========================================
    # UPLOAD DA IMAGEM E MOTOR OCR
    # ==========================================
    st.divider()
    st.subheader("2. Upload do Documento Físico")
    arquivo_nf = st.file_uploader("Anexe a Nota Fiscal (JPG ou PNG)", type=['jpg', 'jpeg', 'png'])

    if arquivo_nf is not None:
        col_img, col_analise = st.columns(2)

        with col_img:
            st.markdown("#### Documento Original")
            imagem_exibicao = Image.open(arquivo_nf)
            st.image(imagem_exibicao, use_container_width=True)

        with col_analise:
            st.markdown("#### Análise do Motor OCR")
            
            with st.spinner("Processando imagem via Tesseract e extraindo matrizes..."):
                arquivo_nf.seek(0) 
                texto = processar_imagem_nf(arquivo_nf)
                resultado = auditar_dados_nf(texto)

            # --- MOTOR DE DECISÃO ---
            cnpj_ocr = resultado['cnpj_encontrado']
            valor_ocr = resultado['valor_total_encontrado']

            st.write("###### Parecer Automatizado:")
            
            if cnpj_ocr:
                cnpj_ocr_limpo = limpar_apenas_numeros(cnpj_ocr)
                cnpj_esperado_limpo = limpar_apenas_numeros(cnpj_esperado)
                
                if cnpj_ocr_limpo == cnpj_esperado_limpo:
                    st.success(f"✅ **CNPJ Validado:** Match perfeito com o fornecedor da API.")
                else:
                    st.error(f"❌ **Divergência de CNPJ!**\n\n**Lido:** {cnpj_ocr}\n**Base TCE:** {cnpj_esperado}")
            else:
                st.warning("⚠️ **CNPJ não localizado:** A qualidade da imagem ou o formato da nota impediram a leitura.")

            if valor_ocr is not None and not pd.isna(valor_esperado):
                if round(valor_ocr, 2) == round(valor_esperado, 2):
                    st.success(f"✅ **Valor Validado:** R$ {valor_ocr:,.2f}")
                else:
                    st.error(f"❌ **Divergência de Valor Financeiro!**\n\n**Lido:** R$ {valor_ocr:,.2f}\n**Base TCE:** R$ {valor_esperado:,.2f}")
            else:
                st.warning("⚠️ **Valor financeiro não localizado** ou valor nulo na base de dados.")
            
            with st.expander("Ver texto bruto extraído (Debug OCR)"):
                st.text(resultado['texto_bruto'])