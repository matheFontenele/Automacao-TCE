import streamlit as st
import pandas as pd
import glob
import os
import re
from main import carregar_municipios

# Definição de Estilo dos Cards (CSS)
CSS_CARDS = """
<style>
    .report-card {
        background-color: #FFFFFF;
        border: 1px solid rgba(0, 0, 0, 0.1); 
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px; 
        border-left: 8px solid #ff4b4b;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        color: #1E1E24 !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .report-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 20px rgba(0, 0, 0, 0.15);
        border-color: #ff4b4b;
    }

    .card-header { color: #666; font-weight: 700; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; }
    .card-vendor { font-size: 1.15rem; font-weight: 800; color: #1E1E24; margin: 5px 0; }
    .card-org { font-size: 0.85rem; color: #ff4b4b; font-weight: 600; margin-bottom: 12px; }
    .card-value { font-family: 'Roboto Mono', monospace; font-weight: 800; color: #15803d; font-size: 1.6rem; }

    .btn-fake {
        background-color: #1E1E24;
        color: white !important;
        padding: 10px 20px;
        border-radius: 6px;
        text-decoration: none;
        font-size: 12px;
        font-weight: bold;
        transition: 0.3s;
        display: inline-block;
    }
    .btn-fake:hover { background-color: #ff4b4b; color: white !important; }
</style>
"""

@st.cache_data(show_spinner="Consolidando base de dados...")
def carregar_e_filtrar(arquivos):
    if not arquivos:
        return pd.DataFrame()
    dfs = []
    for f in arquivos:
        try:
            dfs.append(pd.read_parquet(f))
        except:
            continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def render_consultation_page():
    st.header("🔍 Consulta Detalhada")
    st.markdown(CSS_CARDS, unsafe_allow_html=True)

    # Carrega a lista de municípios usando a função do main.py
    lista_municipios = carregar_municipios()
    opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m['nome_municipio'] for m in lista_municipios}

    # 1. Área de Filtros
    with st.expander("Opções de Filtro", expanded=True):
        
        # Linha 1: Seletores de Escopo (Três colunas iguais)
        col_ano, col_tipo, col_mun = st.columns(3)
        ano_sel = col_ano.selectbox("Ano", [2020, 2021, 2022, 2023, 2024, 2025, 2026], index=6)
        categoria_sel = col_tipo.selectbox("Tipo de Documento", ["Notas de Empenho", "Notas Fiscais", "Notas de Pagamento"])
        municipio_sel = col_mun.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
        
        # Linha 2: Busca Geral (80% da largura) e Botão Realizar Consulta (20% da largura)
        col_busca, col_botao = st.columns([8, 2])
        
        filtro_geral = col_busca.text_input(
            "Busca Geral", 
            placeholder="Nome, CNPJ ou Histórico...",
            label_visibility="visible"
        )
        
        # Alinha verticalmente o botão com o input, adicionando uma margem no topo dele
        col_botao.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
        btn_consultar = col_botao.button("Consultar", use_container_width=True)

    # 2. Lógica de Execução
    if btn_consultar:
        mapa_prefixos = {
            "Notas de Empenho": "notas_empenho",
            "Notas Fiscais": "notas_fiscais",
            "Notas de Pagamento": "notas_pagamentos"
        }

        prefixo = mapa_prefixos[categoria_sel]

        # Define o padrão de arquivos a carregar baseado no município escolhido
        if municipio_sel == "Todos":
            padrao_busca = f"data/{prefixo}_{ano_sel}_*.parquet"
        else:
            # Extrai o código do município do texto do selectbox (ex: "043")
            match = re.search(r'\((\d+)\)', municipio_sel)
            codigo_mun = match.group(1) if match else "*"
            padrao_busca = f"data/{prefixo}_{ano_sel}_*_{codigo_mun}.parquet"

        arquivos = sorted(glob.glob(padrao_busca))

        if arquivos:
            df = carregar_e_filtrar(arquivos)

            if municipio_sel != "Todos" and not df.empty and 'municipio_referencia' in df.columns:
                nome_municipio_real = opcoes_mun[municipio_sel]
                df = df[df['municipio_referencia'].str.upper() == nome_municipio_real.upper()]

            # Aplicação do Filtro de Texto (Busca Geral)
            if filtro_geral and not df.empty:
                if categoria_sel == "Notas de Empenho":
                    mask = (df['nome_negociante'].str.contains(filtro_geral, case=False, na=False)) | \
                           (df['descricao_historico_empenho'].str.contains(filtro_geral, case=False, na=False))
                elif categoria_sel == "Notas de Pagamento":
                    mask = (df['nome_responsavel_pagamento'].str.contains(filtro_geral, case=False, na=False)) | \
                           (df['numero_empenho'].astype(str).str.contains(filtro_geral, case=False, na=False))
                else:
                    mask = (df['cpf_cnpj_emitente'].str.contains(filtro_geral, case=False, na=False)) | \
                           (df['numero_empenho'].astype(str).str.contains(filtro_geral, case=False, na=False))
                df = df[mask]

            # 3. Exibição dos Resultados
            st.subheader(f"LISTA DE {categoria_sel.upper()} - {ano_sel}")
            
            if municipio_sel != "Todos":
                st.write(f"📍 Município selecionado: **{opcoes_mun[municipio_sel]}**")
                
            st.caption(f"Foram encontrados {len(df):,} registros.")

            limite = 50
            for _, row in df.head(limite).iterrows():
                # Lógica para normalizar campos diferentes
                if categoria_sel == "Notas de Empenho":
                    id_doc, entidade, detalhe, valor, label = f"EMPENHO: {row['numero_empenho']}", row['nome_negociante'], row['descricao_historico_empenho'], row['valor_empenhado'], "Empenhado (R$)"
                elif categoria_sel == "Notas de Pagamento":
                    id_doc, entidade, detalhe, valor, label = f"PAGAMENTO: {row['numero_nota_pagamento']}", row['nome_responsavel_pagamento'], f"Ref. Empenho: {row['numero_empenho']}", row['valor_nota_pagamento'], "Pago (R$)"
                else:
                    id_doc, entidade, detalhe, valor, label = f"NF: {row['numero_nota_fiscal']}", f"Emitente: {row['cpf_cnpj_emitente']}", f"Empenho: {row['numero_empenho']}", row['valor_bruto'], "Bruto (R$)"

                # Renderização do Card
                st.markdown(f"""
                    <div class="report-card">
                        <div style="display: flex; justify-content: space-between; align-items: stretch;">
                            <div style="flex: 3; border-right: 1px solid rgba(0,0,0,0.05); padding-right: 25px;">
                                <div class="card-header">{id_doc}</div>
                                <div class="card-vendor">{entidade}</div>
                                <div class="card-org">📍 {row['municipio_referencia']}</div>
                                <div style="font-size: 0.9rem; line-height: 1.5; color: #444; margin-top: 10px;">
                                    {str(detalhe)[:250] + '...' if len(str(detalhe)) > 250 else detalhe}
                                </div>
                            </div>
                            <div style="flex: 1.2; text-align: right; padding-left: 25px; display: flex; flex-direction: column; justify-content: center; background-color: rgba(0,0,0,0.01);">
                                <div style="font-size: 0.7rem; color: #888; font-weight: bold;">{label}</div>
                                <div class="card-value">R$ {valor:,.2f}</div>
                                <div style="margin-top: 15px;"><a href="#" class="btn-fake">🔍 DETALHES</a></div>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            if len(df) > limite:
                st.info(f"Mostrando os {limite} primeiros registros para garantir a performance.")

            # 4. Download do Resultado
            st.divider()
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(f"📥 Exportar Base Completa ({len(df):,} linhas)", csv, f"TCE_{prefixo}_{ano_sel}.csv", "text/csv", use_container_width=True)
        else:
            st.warning(f"Nenhum arquivo encontrado para {categoria_sel} em {ano_sel}. Certifique-se de realizar a extração primeiro.")
    else:
        st.info("Ajuste os filtros acima e clique em '🚀 Consultar' para visualizar os dados.")