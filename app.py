import streamlit as st
import extraction
import consultation

st.set_page_config(page_title="Automação TCE-CE", layout="wide")

# Inicializa o estado de navegação se não existir
if 'modo_tela' not in st.session_state:
    st.session_state.modo_tela = 'Extração'

# Menu lateral de navegação
with st.sidebar:
    st.title("Menu")
    if st.button("📊 Extração", use_container_width=True):
        st.session_state.modo_tela = 'Extração'
    if st.button("🔍 Consulta", use_container_width=True):
        st.session_state.modo_tela = 'Consulta'

# Exibição do conteúdo baseado na escolha
st.title("🚀 Painel de Automação TCE-CE")

if st.session_state.modo_tela == 'Extração':
    extraction.render_extraction_page()
elif st.session_state.modo_tela == 'Consulta':
    consultation.render_consultation_page()