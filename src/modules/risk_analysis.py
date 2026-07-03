import streamlit as st
import pandas as pd
import random
import time
import json
import os

@st.cache_data
def carregar_municipios_json():
    """
    Lê o JSON oficial de municípios e retorna uma lista formatada para o Selectbox.
    O st.cache_data garante que o disco só seja lido uma vez.
    """
    # Procura o arquivo na raiz do projeto (onde o Docker o copia)
    caminho = 'municipios.json'
    
    # Fallback de segurança caso você rode localmente de dentro da pasta src/
    if not os.path.exists(caminho):
        caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'municipios.json')
        
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            # Pega o array dentro de "elements"
            elementos = dados.get('elements', [])
            
            # Formata a string para: "NOME DO MUNICIPIO (CÓDIGO)"
            lista_formatada = [f"{m['nome_municipio']} ({m['codigo_municipio']})" for m in elementos]
            
            # Retorna a lista em ordem alfabética para facilitar a busca do usuário
            return sorted(lista_formatada)
    except Exception as e:
        st.error(f"Erro ao carregar a lista de municípios: {e}")
        return ["Erro de Carregamento"]

def calcular_risco_mock(municipio, valor, mes):
    """
    Função temporária que simula o output do seu futuro modelo Random Forest.
    No futuro, isso será substituído por: model.predict_proba(X)
    """
    time.sleep(1.5) # Simula o tempo de inferência do modelo
    
    # Lógica baseada em peso só para demonstração visual
    risco_base = 30
    if valor > 100000: risco_base += 40
    if mes == "Dezembro": risco_base += 20
    
    probabilidade = min(risco_base + random.randint(-10, 15), 98)
    return probabilidade

def render_risk_page():
    st.header("🧠 Motor de Decisão Comercial - Risco de Inadimplência")
    st.markdown("Avalie a probabilidade de atraso superior a 30 dias em licitações antes de precificar propostas.")
    
    # Carrega a lista dinâmica
    lista_municipios = carregar_municipios_json()
    
    # Tenta definir Sobral como default na interface para agilizar suas análises
    try:
        index_default = next(i for i, v in enumerate(lista_municipios) if "SOBRAL" in v.upper())
    except StopIteration:
        index_default = 0
    
    # ==========================================
    # INPUTS DA EQUIPE COMERCIAL
    # ==========================================
    st.subheader("1. Parâmetros da Licitação")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        municipio = st.selectbox("Órgão / Município", lista_municipios, index=index_default)
    
    with col2:
        valor_contrato = st.number_input("Valor Estimado do Contrato (R$)", min_value=0.0, value=50000.0, step=5000.0)
        
    with col3:
        mes_licitacao = st.selectbox("Mês de Faturamento Previsto", 
                                     ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                                      "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"])
        
    # Botão de gatilho para a IA
    if st.button("🔮 Calcular Risco de Atraso", type="primary", use_container_width=True):
        
        # ==========================================
        # OUTPUT DO MODELO DE MACHINE LEARNING
        # ==========================================
        st.divider()
        st.subheader("2. Parecer Analítico")
        
        with st.spinner("Extraindo padrões do TCE-CE e rodando inferência..."):
            prob_atraso = calcular_risco_mock(municipio, valor_contrato, mes_licitacao)
        
        # Renderização dinâmica baseada no grau de risco
        col_metric, col_recom = st.columns([1, 2])
        
        with col_metric:
            # Cor condicional para o indicador
            cor = "🔴 ALTO" if prob_atraso > 65 else ("🟡 MÉDIO" if prob_atraso > 30 else "🟢 BAIXO")
            
            st.metric(label="Probabilidade de Atraso (>30 dias)", value=f"{prob_atraso}%", delta=cor, delta_color="off")
            
        with col_recom:
            # Pega apenas o nome da cidade, removendo o "(CÓDIGO)" para a mensagem ficar elegante
            nome_cidade_limpo = municipio.split(' (')[0].title()
            
            if prob_atraso > 65:
                st.error("#### ⚠️ ALERTA VERMELHO: Risco Crítico de Caixa")
                st.markdown(f"O modelo detectou que o município de **{nome_cidade_limpo}** possui forte histórico de reter pagamentos nestas circunstâncias (Valores próximos a R$ {valor_contrato:,.2f} no mês de {mes_licitacao}).")
                st.markdown("**Recomendação Comercial:** Embutir taxa de risco no preço da proposta. Aumentar margem em pelo menos **18% a 25%** para compensar custo de capital parado.")
            
            elif prob_atraso > 30:
                st.warning("#### ⚖️ ALERTA AMARELO: Risco Moderado")
                st.markdown(f"Pode haver um leve atraso. Cuidado com o fluxo de caixa para os próximos meses caso **{nome_cidade_limpo}** seja um cliente âncora.")
                st.markdown("**Recomendação Comercial:** Manter margem padrão, mas preparar fundo de reserva para absorver um possível atraso de 45 dias.")
                
            else:
                st.success("#### ✅ ALERTA VERDE: Bom Pagador")
                st.markdown(f"O histórico aponta que pagamentos na faixa de R$ {valor_contrato:,.2f} costumam ser honrados no prazo estabelecido por **{nome_cidade_limpo}**.")
                st.markdown("**Recomendação Comercial:** Ambiente seguro. Operar com margem agressiva para ganhar a licitação.")