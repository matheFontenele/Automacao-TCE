import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.extraction import render_extraction_page
from src.modules.consultation import render_consultation_page
from src.modules.risk_analysis import render_risk_page 
# 1. NOVA IMPORTAÇÃO: Módulo de Auditoria Visual (OCR)
from src.modules.audit_page import render_audit_page 

st.set_page_config(page_title="Automação TCE-CE", layout="wide")

# Estilização para o Menu Superior
st.markdown("""
    <style>
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
    div.stButton > button:hover {
        background-color: #2D2D35 !important;
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.4) !important;
    }
    button:focus:not(:active) {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
    }
    </style>
""", unsafe_allow_html=True)

# Inicializa o estado de navegação
if 'modo_tela' not in st.session_state:
    st.session_state.modo_tela = 'Extração'

st.title("🤖 Painel de Automação TCE-CE")

# 2. COLUNAS ATUALIZADAS: Adicionado um espaço para o 4º botão e reduzido o espaçador
col_nav1, col_nav2, col_nav3, col_nav4, col_spacer = st.columns([1.0, 1.0, 1.0, 1.0, 4])

with col_nav1:
    if st.button("📊 Extração", key="btn_ext", 
                 type="primary" if st.session_state.modo_tela == 'Extração' else "secondary"):
        st.session_state.modo_tela = 'Extração'
        st.rerun()

with col_nav2:
    if st.button("🔍 Consulta", key="btn_con", 
                 type="primary" if st.session_state.modo_tela == 'Consulta' else "secondary"):
        st.session_state.modo_tela = 'Consulta'
        st.rerun()

with col_nav3:
    if st.button("🧠 Motor de Risco", key="btn_risk", 
                 type="primary" if st.session_state.modo_tela == 'Risco' else "secondary"):
        st.session_state.modo_tela = 'Risco'
        st.rerun()

# 3. NOVO BOTÃO: Auditoria Antifraude
with col_nav4:
    if st.button("🔎 Auditoria", key="btn_audit", 
                 type="primary" if st.session_state.modo_tela == 'Auditoria' else "secondary"):
        st.session_state.modo_tela = 'Auditoria'
        st.rerun()
        
st.divider()

# 4. ROTEADOR ATUALIZADO
if st.session_state.modo_tela == 'Extração':
    render_extraction_page()
elif st.session_state.modo_tela == 'Consulta':
    render_consultation_page()
elif st.session_state.modo_tela == 'Risco':
    render_risk_page()
elif st.session_state.modo_tela == 'Auditoria':
    render_audit_page()