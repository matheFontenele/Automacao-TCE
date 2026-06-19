"""
Painel de Automação TCE-CE
Aplicação Streamlit com navegação dinâmica e estrutura modular
"""

import sys
import os
import streamlit as st
from src.extraction.extraction import render_extraction_page
from src.consultation.consutation import render_consultation_page
from src.compare.compare import render_aba_comparacao

# ============================================================================
# CONFIGURAÇÃO DO PYTHONPATH
# ============================================================================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ============================================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================================
st.set_page_config(
    page_title="Automação TCE-CE",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# ESTILIZAÇÃO CSS
# ============================================================================
STYLES = """
    <style>
    /* Botões padrão */
    div.stButton > button {
        width: 100% !important;
        border-radius: 8px !important;
        height: 3.5em !important;
        background-color: #1E1E24 !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        transition: all 0.3s ease-in-out !important;
    }
    
    /* Hover */
    div.stButton > button:hover {
        background-color: #2D2D35 !important;
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
        transform: translateY(-2px) !important;
    }
    
    /* Botão ativo (primary) */
    div.stButton > button[kind="primary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.4) !important;
    }
    
    div.stButton > button[kind="primary"]:hover {
        background-color: #ff3333 !important;
        box-shadow: 0 6px 16px rgba(255, 75, 75, 0.6) !important;
    }
    
    /* Foco */
    button:focus:not(:active) {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
    }
    
    /* Divider */
    hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
    }
    </style>
"""

st.markdown(STYLES, unsafe_allow_html=True)

# ============================================================================
# MAPA DE PÁGINAS (Estrutura escalável)
# ============================================================================
PAGES = {
    'Extração': {
        'icon': '📊',
        'func': render_extraction_page,
        'description': 'Extrair dados de documentos PDF'
    },
    'Consulta': {
        'icon': '🔍',
        'func': render_consultation_page,
        'description': 'Consultar e analisar dados extraídos'
    },
    'Comparação': {
        'icon': '⚙️',
        'func': render_aba_comparacao,
        'description': 'Comparar múltiplos registros'
    },
}

# ============================================================================
# INICIALIZAR ESTADO DA SESSÃO
# ============================================================================
if 'modo_tela' not in st.session_state:
    st.session_state.modo_tela = 'Extração'

# ============================================================================
# HEADER E TÍTULO
# ============================================================================
st.title("🤖 Painel de Automação TCE-CE")
st.markdown("**Sistema de Processamento Inteligente de Documentos Fiscais**")

# ============================================================================
# BARRA DE NAVEGAÇÃO DINÂMICA
# ============================================================================
cols = st.columns([1, 1, 1, 5])

for idx, (page_name, page_info) in enumerate(PAGES.items()):
    with cols[idx]:
        is_active = st.session_state.modo_tela == page_name
        
        if st.button(
            f"{page_info['icon']} {page_name}",
            key=f"btn_{page_name}",
            type="primary" if is_active else "secondary",
            use_container_width=True
        ):
            st.session_state.modo_tela = page_name
            st.rerun()

st.divider()

# ============================================================================
# RENDERIZAR PÁGINA ATIVA
# ============================================================================
try:
    PAGES[st.session_state.modo_tela]['func']()
except Exception as e:
    st.error(f"❌ Erro ao carregar a página: {str(e)}")
    st.info("Contate o administrador se o problema persistir.")