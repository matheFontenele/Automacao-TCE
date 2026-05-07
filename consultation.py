import streamlit as st
import pandas as pd
import glob
import os

# 1. Configuração de Estilo Adaptativo (CSS)
st.markdown("""
    <style>
    /* 1. ESTILO DOS BOTÕES DE SISTEMA (Menu, Extração e Filtros) */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        background-color: #1E1E24 !important; /* Grafite Escuro */
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        font-weight: 600;
        transition: all 0.3s ease-in-out;
    }

    .stButton > button:hover {
        background-color: #2D2D35 !important;
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
        transform: translateY(-1px);
    }

    /* Destaque para o botão da tela ativa */
    .stButton > button[kind="primary"] {
        background-color: #ff4b4b !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.3);
    }

    /* 2. ESTILO DOS CARDS DE RESULTADOS (Melhor Divisão) */
    .report-card {
        background-color: var(--secondary-background-color);
        /* Borda completa mais escura para destacar do fundo */
        border: 1px solid rgba(128, 128, 128, 0.3); 
        border-radius: 12px;
        padding: 24px;
        /* Aumentado para evidenciar a separação entre registros */
        margin-bottom: 25px; 
        border-left: 10px solid #ff4b4b;
        color: var(--text-color);
        /* Sombra projetada para dar profundidade */
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.2); 
        transition: all 0.3s ease;
    }

    .report-card:hover {
        transform: scale(1.01); /* Leve expansão ao focar no card */
        border-color: #ff4b4b;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
    }

    /* 3. TEXTOS INTERNOS DO CARD */
    .card-header { 
        color: #ff4b4b; 
        font-weight: bold; 
        font-size: 0.75rem; 
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }
    
    .card-vendor { 
        font-size: 1.2rem; 
        font-weight: 800;
        margin: 8px 0;
        line-height: 1.2;
    }

    .card-org {
        font-size: 0.95rem;
        font-weight: 500;
        opacity: 0.85;
        margin-bottom: 15px;
    }

    .card-value { 
        font-family: 'Roboto Mono', monospace;
        font-weight: 700; 
        color: #28a745; 
        font-size: 1.5rem;
    }

    /* 4. BOTÃO DE DETALHES DENTRO DO CARD */
    .btn-fake {
        background-color: #1E1E24;
        color: white !important;
        padding: 8px 18px;
        border-radius: 6px;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        text-decoration: none;
        display: inline-block;
        margin-top: 15px;
        font-weight: bold;
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: 0.3s;
    }

    .btn-fake:hover {
        background-color: #ff4b4b;
        border-color: #ff4b4b;
        box-shadow: 0 4px 10px rgba(255, 75, 75, 0.2);
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner="Consolidando base de dados...")
def carregar_e_filtrar(arquivos):
    if not arquivos:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in arquivos], ignore_index=True)

def render_consultation_page():
    st.header("🔍 Consulta Detalhada")

    # Filtros Superiores
    with st.expander("🎯 Opções de Filtro", expanded=True):
        c1, c2, c3 = st.columns(3)
        ano_sel = c1.selectbox("Ano", [2020, 2021, 2022, 2023, 2024, 2025, 2026], index=6)
        categoria_sel = c2.selectbox("Tipo de Documento", ["Notas de Empenho", "Notas Fiscais", "Notas de Pagamento"])
        filtro_geral = c3.text_input("Busca Geral", placeholder="Nome ou Histórico...")

    mapa_prefixos = {
        "Notas de Empenho": "notas_empenho",
        "Notas Fiscais": "notas_fiscais",
        "Notas de Pagamento": "notas_pagamentos"
    }

    prefixo = mapa_prefixos[categoria_sel]
    arquivos = glob.glob(f"data/{prefixo}_{ano_sel}_*.parquet")

    if arquivos:
        df = carregar_e_filtrar(arquivos)

        # Lógica de Filtro
        if filtro_geral:
            if categoria_sel == "Notas de Empenho":
                mask = (df['nome_negociante'].str.contains(filtro_geral, case=False, na=False)) | \
                       (df['descricao_historico_empenho'].str.contains(filtro_geral, case=False, na=False))
            elif categoria_sel == "Notas de Pagamento":
                mask = df['nome_responsavel_pagamento'].str.contains(filtro_geral, case=False, na=False)
            else:
                mask = (df['municipio_referencia'].str.contains(filtro_geral, case=False, na=False)) | \
                       (df['cpf_cnpj_emitente'].str.contains(filtro_geral, case=False, na=False))
            df = df[mask]

        st.subheader(f"LISTA DE {categoria_sel.upper()} - {ano_sel}")
        st.caption(f"Foram encontrados {len(df):,} registros.")

        limite = 100
        for _, row in df.head(limite).iterrows():
            # Mapeamento Dinâmico
            if categoria_sel == "Notas de Empenho":
                id_doc, entidade, detalhe, valor, label = f"EMPENHO: {row['numero_empenho']}", row['nome_negociante'], row['descricao_historico_empenho'], row['valor_empenhado'], "Empenhado (R$)"
            elif categoria_sel == "Notas de Pagamento":
                id_doc, entidade, detalhe, valor, label = f"PAGAMENTO: {row['numero_nota_pagamento']}", row['nome_responsavel_pagamento'], f"Empenho Ref: {row['numero_empenho']}", row['valor_nota_pagamento'], "Pago (R$)"
            else:
                id_doc, entidade, detalhe, valor, label = f"NF: {row['numero_nota_fiscal']}", f"Emitente: {row['cpf_cnpj_emitente']}", f"Empenho: {row['numero_empenho']}", row['valor_bruto'], "Bruto (R$)"

            # HTML do Card com Alinhamento Corrigido
            st.markdown(f"""
                <div class="report-card">
                    <div style="display: flex; justify-content: space-between; align-items: stretch;">
            
                        <div style="flex: 3; border-right: 1px solid rgba(128,128,128,0.3); padding-right: 25px;">
                            <div class="card-header">{id_doc}</div>
                            <div class="card-vendor">{entidade}</div>
                            <div class="card-org">📍 {row['municipio_referencia']}</div>
                
                            <div style="font-size: 0.9rem; line-height: 1.6; opacity: 0.9; margin-top: 10px; color: var(--text-color);">
                                {str(detalhe)[:280] + '...' if len(str(detalhe)) > 280 else detalhe}
                         </div>
                     </div>

                     <div style="flex: 1.2; text-align: right; padding-left: 25px; display: flex; flex-direction: column; justify-content: center; background-color: rgba(128,128,128,0.03); border-radius: 0 8px 8px 0;">
                          <div style="font-size: 0.75rem; opacity: 0.7; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px;">
                             {label}
                          </div>
                           <div class="card-value">
                              R$ {valor:,.2f}
                         </div>
                          <div style="margin-top: 15px;">
                              <a href="#" class="btn-fake">🔍 DETALHES</a>
                            </div>
                       </div>
            
                 </div>
               </div>
            """, unsafe_allow_html=True)

        if len(df) > limite:
            st.warning(f"Exibindo os primeiros {limite} resultados por performance.")

        st.divider()
        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(f"📥 Exportar Resultado Completo ({len(df):,} linhas)", csv, f"TCE_{prefixo}_{ano_sel}.csv", "text/csv", use_container_width=True)
    else:
        st.warning(f"Nenhum arquivo de {categoria_sel} encontrado para o ano {ano_sel}.")