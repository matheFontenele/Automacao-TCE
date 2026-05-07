import streamlit as st
import pandas as pd
import glob
import os

def aba_consulta():
    st.header("🔍 Consulta Detalhada")

    # 1. Filtros Superiores (Similar ao print que você enviou)
    with st.expander("Opções de Filtro", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            ano_sel = st.selectbox("Ano", options=[2024, 2025, 2026], index=2)
        with col2:
            categoria_sel = st.selectbox("Tipo de Documento", 
                                         options=["Notas de Empenho", "Notas Fiscais", "Liquidações"])
        with col3:
            # Esse campo será usado para filtrar o DataFrame após o carregamento
            filtro_texto = st.text_input("Histórico / Fornecedor", placeholder="Digite para buscar...")

    # Mapeamento para buscar os arquivos certos
    mapa_prefixos = {
        "Notas de Empenho": "notas_empenho",
        "Notas Fiscais": "notas_fiscais",
        "Liquidações": "liquidacoes"
    }

    # 2. Carregamento dos Dados
    prefixo = mapa_prefixos[categoria_sel]
    # Busca todos os arquivos daquela categoria e ano
    caminho_busca = f"data/{prefixo}_{ano_sel}_*.parquet"
    arquivos = glob.glob(caminho_busca)

    if arquivos:
        with st.spinner(f"Consolidando {len(arquivos)} arquivos..."):
            # Lê e concatena todos os parquets encontrados
            df = pd.concat([pd.read_parquet(f) for f in arquivos], ignore_index=True)
        
        # 3. Aplicação de Filtros Dinâmicos no Pandas
        if filtro_texto:
            # Exemplo de filtro que busca em múltiplas colunas (ajuste conforme os nomes reais do seu CSV/Parquet)
            mascara = (df.astype(str).apply(lambda x: x.str.contains(filtro_texto, case=False)).any(axis=1))
            df = df[mascara]

        # 4. Exibição da Tabela (Estilizada)
        st.subheader(f"Lista de {categoria_sel} - {ano_sel}")
        st.caption(f"Foram encontrados {len(df)} registros")

        # Formatação de valores (se as colunas existirem)
        # Ex: df['valor_pago'] = df['valor_pago'].map('R$ {:,.2f}'.format)

        st.dataframe(
            df, 
            use_container_width=True,
            column_config={
                "link_documento": st.column_config.LinkColumn("Ver Mais") # Caso tenha link
            }
        )
        
        # Botão de Exportação (Similar ao "Opções para exportação" do print)
        st.download_button(
            label="📥 Exportar Consulta (CSV)",
            data=df.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"consulta_{prefixo}_{ano_sel}.csv",
            mime="text/csv",
        )

    else:
        st.warning(f"Nenhum dado de {categoria_sel} disponível para o ano {ano_sel}. Realize a extração primeiro.")

# Chamada na estrutura principal
# aba_consulta() 