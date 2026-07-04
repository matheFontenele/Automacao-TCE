import streamlit as st
import pandas as pd
import glob
import os
import re
import json
import fitz
from PIL import Image

from src.modules.ocr_engine import processar_documento, auditar_dados_nf

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
    if pd.isna(texto) or not texto:
        return ""
    return re.sub(r'[^0-9]', '', str(texto))

def render_audit_page():
    st.header("🔎 Auditoria Antifraude - Motor Híbrido (OCR & PDF)")
    st.markdown("Reconciliação automática entre Notas Fiscais físicas/digitais e a base de dados oficial do TCE-CE.")

    df_empenhos = carregar_empenhos_reais()
    mapa_municipios = carregar_mapa_municipios()

    if df_empenhos.empty:
        st.warning("⚠️ Nenhum dado de empenho encontrado. Vá na aba de Extração e baixe os dados do TCE primeiro.")
        return

    st.subheader("1. Selecione o Contrato (Base TCE-CE)")
    
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        if 'codigo_municipio' in df_empenhos.columns:
            codigos_baixados = df_empenhos['codigo_municipio'].dropna().unique().tolist()
            opcoes_muns = ["Todos"] + sorted([mapa_municipios.get(cod, f"Desconhecido ({cod})") for cod in codigos_baixados])
            
            mun_selecionado = st.selectbox("📍 Filtrar por Município", opcoes_muns)
            
            if mun_selecionado != "Todos":
                mun_filtro = mun_selecionado.split('(')[-1].replace(')', '').strip()
            else:
                mun_filtro = "Todos"
        else:
            mun_filtro = "Todos"
            
    with col_filtro2:
        busca_fornecedor = st.text_input("🏢 Buscar Fornecedor (Nome ou CNPJ)", placeholder="Ex: CONSTRUTORA ou 123456")

    df_filtrado = df_empenhos.copy()
    
    if mun_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado['codigo_municipio'] == mun_filtro]
        
    if busca_fornecedor:
        termo_busca = busca_fornecedor.lower()
        df_filtrado = df_filtrado[
            df_filtrado['nome_negociante'].astype(str).str.lower().str.contains(termo_busca, na=False) |
            df_filtrado['numero_documento_negociante'].astype(str).str.lower().str.contains(termo_busca, na=False)
        ]

    if df_filtrado.empty:
        st.warning("Nenhum contrato encontrado com os filtros aplicados. Tente limpar a busca.")
        return 
        
    opcoes_display = df_filtrado['numero_empenho'].astype(str) + " — " + df_filtrado['nome_negociante'].astype(str)
    empenho_selecionado = st.selectbox("Selecione o Empenho Alvo", opcoes_display)
    
    numero_alvo = empenho_selecionado.split(" — ")[0]
    linha_alvo = df_filtrado[df_filtrado['numero_empenho'].astype(str) == numero_alvo].iloc[0]

    cnpj_esperado = str(linha_alvo['numero_documento_negociante'])
    valor_esperado = pd.to_numeric(linha_alvo['valor_empenhado'], errors='coerce')
    nome_mun_info = mapa_municipios.get(str(linha_alvo['codigo_municipio']), str(linha_alvo['codigo_municipio']))
    
    st.info(f"**📍 Órgão:** {nome_mun_info} | **📄 Empenho:** {linha_alvo['numero_empenho']} | **🏢 Fornecedor:** {cnpj_esperado} | **💰 Valor Empenhado:** R$ {valor_esperado:,.2f}")

    # ==========================================
    # UPLOAD DO DOCUMENTO E MOTOR OCR
    # ==========================================
    st.divider()
    st.subheader("2. Upload do Documento Físico ou Digital")
    
    # Suporte a múltiplas extensões ativado
    arquivo_nf = st.file_uploader("Anexe o Documento (JPG, PNG, PDF ou TXT)", type=['jpg', 'jpeg', 'png', 'pdf', 'txt'])

    if arquivo_nf is not None:
        col_doc, col_analise = st.columns(2)
        extensao_arq = arquivo_nf.name.split('.')[-1].lower()

        with col_doc:
            st.markdown("#### Documento Original")
            
            # Adapta a interface para não quebrar com arquivos não-imagem
            if extensao_arq in ['jpg', 'jpeg', 'png']:
                imagem_exibicao = Image.open(arquivo_nf)
                st.image(imagem_exibicao, use_container_width=True)
            elif extensao_arq == 'pdf':
                st.info("📄 Arquivo PDF carregado com sucesso. O motor híbrido extrairá o texto nativo ou rasterizará as imagens necessárias.")
            elif extensao_arq == 'txt':
                st.info("📝 Arquivo de Texto carregado com sucesso.")

        with col_analise:
            st.markdown("#### Análise do Motor Híbrido")
            
            with st.spinner("Extraindo e processando dados estruturados..."):
                arquivo_nf.seek(0) 
                
                # Envia o arquivo para o roteador tomar a decisão de extração
                texto = processar_documento(arquivo_nf)
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
                st.warning("⚠️ **CNPJ não localizado:** A qualidade do arquivo ou o formato impediram a leitura.")

            if valor_ocr is not None and not pd.isna(valor_esperado):
                if round(valor_ocr, 2) == round(valor_esperado, 2):
                    st.success(f"✅ **Valor Validado:** R$ {valor_ocr:,.2f}")
                else:
                    st.error(f"❌ **Divergência de Valor Financeiro!**\n\n**Lido:** R$ {valor_ocr:,.2f}\n**Base TCE:** R$ {valor_esperado:,.2f}")
            else:
                st.warning("⚠️ **Valor financeiro não localizado** ou valor nulo na base de dados.")
            
            with st.expander("Ver texto bruto extraído (Debug Engine)"):
                st.text(resultado['texto_bruto'])