import streamlit as st
import pandas as pd
import glob
import os

# Função de cache para acelerar o carregamento dos dados já processados
@st.cache_data(show_spinner="Carregando base de dados da memória...")
def carregar_dados_cached(arquivos):
    if not arquivos:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in arquivos], ignore_index=True)

def render_consultation_page():
    st.header("🔍 Consulta Detalhada")

    # 1. Filtros Superiores (Inspirados no Portal da Transparência)
    with st.expander("🎯 Opções de Filtro", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            # Incluindo todo o intervalo que você está baixando
            anos_disponiveis = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
            ano_sel = st.selectbox("Ano", options=anos_disponiveis, index=5)
        with col2:
            categoria_sel = st.selectbox("Tipo de Documento", 
                                         options=["Notas de Empenho", "Notas Fiscais", "Liquidações", "Notas de Pagamento"])
        with col3:
            filtro_texto = st.text_input("Busca Geral (Histórico)", placeholder="Palavra-chave no histórico...")

        col4, col5 = st.columns(2)
        with col4:
            orgao_sel = st.text_input("Filtrar por Órgão", placeholder="Ex: Secretaria de Educação")
        with col5:
            fornecedor_sel = st.text_input("Fornecedor", placeholder="CPF, CNPJ ou Nome")

    # Mapeamento para buscar os arquivos Parquet gerados pelo seu extrator
    mapa_prefixos = {
        "Notas de Empenho": "notas_empenho",
        "Notas Fiscais": "notas_fiscais",
        "Liquidações": "liquidacoes",
        "Notas de Pagamento": "notas_pagamentos"
    }

    # 2. Carregamento dos Dados
    prefixo = mapa_prefixos[categoria_sel]
    caminho_busca = f"data/{prefixo}_{ano_sel}_*.parquet"
    arquivos = glob.glob(caminho_busca)

    if arquivos:
        with st.spinner(f"Consolidando {len(arquivos)} arquivos de {ano_sel}..."):
            # Concatena os parquets (muito mais rápido que CSV para 700k linhas)
            df = pd.concat([pd.read_parquet(f) for f in arquivos], ignore_index=True)
        
        # 3. Aplicação dos Filtros Específicos (Pandas)
        if orgao_sel:
            # Ajuste 'nome_orgao' conforme o nome real da coluna no seu dado do TCE
            col_orgao = 'nome_orgao' if 'nome_orgao' in df.columns else 'municipio_referencia'
            df = df[df[col_orgao].str.contains(orgao_sel, case=False, na=False)]
            
        if fornecedor_sel:
            # Ajuste 'nome_fornecedor' conforme a coluna real
            col_forn = 'nome_fornecedor' if 'nome_fornecedor' in df.columns else df.columns[0]
            df = df[df[col_forn].str.contains(fornecedor_sel, case=False, na=False)]

        if filtro_texto:
            mascara = (df.astype(str).apply(lambda x: x.str.contains(filtro_texto, case=False)).any(axis=1))
            df = df[mascara]

        # 4. Exibição da Tabela e Prevenção de MessageSizeError
        st.subheader(f"Lista de {categoria_sel} - {ano_sel}")
        st.caption(f"Foram encontrados {len(df):,} registros no total.")

        # Importante: O Streamlit não aguenta renderizar 500MB de uma vez.
        # Limitamos a visualização, mas mantemos o download completo.
        limite_view = 1000
        if len(df) > limite_view:
            st.warning(f"⚠️ Apenas os primeiros {limite_view} registros estão visíveis para manter a performance. Use os filtros acima para refinar sua busca.")

        # Tentativa de formatação monetária automática para colunas de valor
        colunas_valor = [c for c in df.columns if 'valor' in c.lower()]
        format_dict = {col: "R$ {:,.2f}" for col in colunas_valor}

        st.dataframe(
            df.head(limite_view), 
            use_container_width=True,
            hide_index=True,
            column_config={
                **{col: st.column_config.NumberColumn(col, format="R$ %.2f") for col in colunas_valor},
                "link_documento": st.column_config.LinkColumn("🔗 Ver Documento")
            }
        )
        
        # 5. Exportação (Sempre exporta o DF filtrado INTEIRO, ignorando o limite de 1000)
        st.divider()
        st.download_button(
            label=f"📥 Exportar Resultado Completo ({len(df):,} linhas)",
            data=df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig'),
            file_name=f"TCE_{prefixo}_{ano_sel}.csv",
            mime="text/csv",
            use_container_width=True
        )

    else:
        st.warning(f"Nenhum dado de {categoria_sel} encontrado para o ano {ano_sel}.")
        st.info("Verifique se o extrator no terminal já finalizou esse período.")