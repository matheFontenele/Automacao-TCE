import streamlit as st
import pandas as pd
import glob
import os
import re
from PIL import Image
from src.modules.ocr_engine import processar_imagem_nf, auditar_dados_nf

@st.cache_data
def carregar_empenhos_reais():
    """
    Lê os arquivos Parquet de empenho gerados pelo motor de extração.
    Usa cache para não sobrecarregar a memória ao trocar de tela.
    """
    # Procura na pasta local ou na raiz do contêiner
    caminho_base = "data/"
    if not os.path.exists(caminho_base):
        caminho_base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        
    arquivos = glob.glob(os.path.join(caminho_base, "notas_empenho_*.parquet"))
    
    if not arquivos:
        return pd.DataFrame()
        
    # Empilha todos os parquets encontrados
    df = pd.concat([pd.read_parquet(f) for f in arquivos], ignore_index=True)
    
    # Remove duplicatas caso o mesmo empenho tenha vindo em meses diferentes
    df = df.drop_duplicates(subset=['numero_empenho'])
    
    # Filtra colunas nulas ou zumbis
    df = df.dropna(subset=['numero_empenho', 'numero_documento_negociante'])
    return df

def limpar_apenas_numeros(texto):
    """Remove pontos, barras e traços de CNPJs para garantir o match perfeito."""
    if pd.isna(texto) or not texto:
        return ""
    return re.sub(r'[^0-9]', '', str(texto))

def render_audit_page():
    st.header("🔎 Auditoria Antifraude - Visão Computacional")
    st.markdown("Reconciliação automática entre Notas Fiscais físicas e a base de dados oficial do TCE-CE.")

    # 1. CARREGAMENTO DOS DADOS REAIS
    df_empenhos = carregar_empenhos_reais()

    if df_empenhos.empty:
        st.warning("⚠️ Nenhum dado de empenho encontrado. Vá na aba de Extração e baixe os dados do TCE primeiro.")
        return

    st.subheader("1. Selecione o Contrato (Base TCE-CE)")
    
    # Cria uma lista bonita para o usuário ler: "2026.01.001 - EMPRESA X"
    opcoes_display = df_empenhos['numero_empenho'].astype(str) + " — " + df_empenhos['nome_negociante'].astype(str)
    
    empenho_selecionado = st.selectbox("Busque pelo Empenho ou Fornecedor", opcoes_display)
    
    # Isola a linha exata que o usuário escolheu
    numero_alvo = empenho_selecionado.split(" — ")[0]
    linha_alvo = df_empenhos[df_empenhos['numero_empenho'].astype(str) == numero_alvo].iloc[0]

    # Prepara as variáveis esperadas (Gabarito)
    cnpj_esperado = str(linha_alvo['numero_documento_negociante'])
    valor_esperado = pd.to_numeric(linha_alvo['valor_empenhado'], errors='coerce')
    
    st.info(f"**Alvo Selecionado:** {linha_alvo['numero_empenho']} | **Fornecedor:** {cnpj_esperado} | **Valor Empenhado:** R$ {valor_esperado:,.2f}")

    # 2. UPLOAD DA IMAGEM E MOTOR OCR
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

            # --- MOTOR DE DECISÃO (A GRANDE COMPARAÇÃO) ---
            cnpj_ocr = resultado['cnpj_encontrado']
            valor_ocr = resultado['valor_total_encontrado']

            st.write("###### Parecer Automatizado:")
            
            # Checagem de CNPJ (Com higienização de pontuação)
            if cnpj_ocr:
                cnpj_ocr_limpo = limpar_apenas_numeros(cnpj_ocr)
                cnpj_esperado_limpo = limpar_apenas_numeros(cnpj_esperado)
                
                if cnpj_ocr_limpo == cnpj_esperado_limpo:
                    st.success(f"✅ **CNPJ Validado:** Match perfeito com o fornecedor da API.")
                else:
                    st.error(f"❌ **Divergência de CNPJ!**\n\n**Lido:** {cnpj_ocr}\n**Base TCE:** {cnpj_esperado}")
            else:
                st.warning("⚠️ **CNPJ não localizado:** A qualidade da imagem ou o formato da nota impediram a leitura.")

            # Checagem de Valor (Com margem de tolerância para centavos)
            if valor_ocr is not None and not pd.isna(valor_esperado):
                # Arredonda para 2 casas para evitar quebra por floats (ex: 15.00 vs 15.00000001)
                if round(valor_ocr, 2) == round(valor_esperado, 2):
                    st.success(f"✅ **Valor Validado:** R$ {valor_ocr:,.2f}")
                else:
                    st.error(f"❌ **Divergência de Valor Financeiro!**\n\n**Lido:** R$ {valor_ocr:,.2f}\n**Base TCE:** R$ {valor_esperado:,.2f}")
            else:
                st.warning("⚠️ **Valor financeiro não localizado** ou valor nulo na base de dados.")
            
            with st.expander("Ver texto bruto extraído (Debug OCR)"):
                st.text(resultado['texto_bruto'])