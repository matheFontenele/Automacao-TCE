# details_modal.py
import streamlit as st
import pandas as pd
import glob
import re

# IMPORTANDO O GERADOR DE PDF ISOLADO
from gerador_pdf import gerar_pdf_empenho

# ==============================================================================
# FUNÇÕES AUXILIARES DO MODAL
# ==============================================================================
def formatar_moeda_modal(valor):
    try:
        if pd.isna(valor) or valor is None:
            return "0,00"
        val_float = float(valor)
        return f"{val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

def formatar_data_modal(data_raw):
    try:
        if pd.isna(data_raw) or data_raw is None:
            return "Não Informada"
        data_str = str(data_raw).split('T')[0]
        partes = data_str.split('-')
        if len(partes) == 3:
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
        return data_str
    except Exception:
        return "Não Informada"

def obter_caminho_arquivos_modal(prefixo, ano, codigo_mun):
    if codigo_mun == "Todos":
        return sorted(glob.glob(f"data/{prefixo}_{ano}_*.parquet"))
    return sorted(glob.glob(f"data/{prefixo}_{ano}_*_{codigo_mun}.parquet"))

def carregar_e_filtrar_modal(arquivos):
    """Carrega os arquivos dinamicamente em memória apenas para o escopo do modal."""
    if not arquivos:
        return pd.DataFrame()
    dfs = []
    for f in arquivos:
        try:
            dfs.append(pd.read_parquet(f))
        except:
            continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# ==============================================================================
# DIALOG (MODAL) EXPORTADO
# ==============================================================================
@st.dialog("📋 Detalhes do Empenho", width="large")
def exibir_modal_detalhes(row, categoria, ano, codigo_mun):
    
    # --------------------------------------------------------------------------
    # 1. DEFINIÇÃO DAS VARIÁVEIS DE BUSCA NO TOPO
    # (Evita NameError em chamadas assíncronas ou fragmentadas do Streamlit)
    # --------------------------------------------------------------------------
    num_empenho_busca = str(row.get('numero_empenho', '')).strip()
    cod_mun_busca = str(row.get('codigo_municipio', '')).strip()
    
    # Cabeçalho Principal do Modal
    st.write(f"### Empenho Nº {row.get('numero_empenho', 'N/A')}")
    st.caption(f"📍 {row.get('municipio_referencia', 'Não Informado')} — Exercício Orçamentário: {str(row.get('exercicio_orcamento', ''))[:4]}")
    st.divider()

    # ==============================================================================
    # SEÇÃO 1: INFORMAÇÕES DO EMPENHO
    # ==============================================================================
    st.markdown("#### 📄 INFORMAÇÕES DO EMPENHO")
    
    col_emp1, col_emp2 = st.columns(2)
    with col_emp1:
        st.markdown(f"**Número do empenho:** `{row.get('numero_empenho', 'N/A')}`")
        
        # Data de emissão tratando empenho/fiscais/pagamentos
        data_emissao = row.get('data_emissao_empenho', row.get('data_emissao', row.get('data_nota_pagamento')))
        st.markdown(f"**Data:** {formatar_data_modal(data_emissao)}")
        
        # Valor do empenho
        valor_emp = row.get('valor_empenhado', row.get('valor_bruto', row.get('valor_nota_pagamento', 0.0)))
        st.markdown(f"**Valor:** `R$ {formatar_moeda_modal(valor_emp)}`")

    with col_emp2:
        # Fornecedor / Credor
        fornecedor = row.get('nome_negociante', row.get('nome_responsavel_pagamento', 'Não Informado'))
        st.markdown(f"**Fornecedor:** {fornecedor}")
        
        # CPF/CNPJ Documento do Negociante
        cnpj_fornecedor = row.get('numero_documento_negociante', row.get('cpf_cnpj_emitente', row.get('cpf_responsavel_pagamento', 'Ocultado')))
        st.markdown(f"**CNPJ/CPF Fornecedor:** `{cnpj_fornecedor}`")
        
        # Modalidade da Licitação
        modalidade_licitacao = row.get('tipo_processo_licitatorio', 'N/A')
        st.markdown(f"**Modalidade de Licitação:** `{modalidade_licitacao}`")

    st.divider()

    # ==============================================================================
    # SEÇÃO 2: INFORMAÇÕES DE ORÇAMENTO
    # ==============================================================================
    st.markdown("#### 🏛️ INFORMAÇÕES DE ORÇAMENTO")
    
    col_orc1, col_orc2 = st.columns(2)
    with col_orc1:
        unidade_gestora = f"{row.get('municipio_referencia', 'N/A')} - U.O. {row.get('codigo_unidade_orcamentaria', 'N/A')}"
        st.markdown(f"**Unidade Gestora:** {unidade_gestora}")

    with col_orc2:
        st.markdown(f"**Órgão:** `{row.get('codigo_orgao', 'N/A')}`")

    st.divider()

    # ==============================================================================
    # SEÇÃO 3: HISTÓRICO / DESCRIÇÃO
    # ==============================================================================
    st.markdown("#### 📜 Histórico / Descrição")
    st.info(row.get('descricao_historico_empenho', 'Sem descrição adicional cadastrada.'))

    st.divider()

    # ==============================================================================
    # SEÇÃO 4: MOVIMENTAÇÕES DE LIQUIDAÇÃO E PAGAMENTOS (LADO A LADO)
    # ==============================================================================
    col_liq, col_pag = st.columns(2)

    # --- 1. Movimentações da Liquidação (Lado Esquerdo) ---
    with col_liq:
        st.markdown("#### 🔍 MOVIMENTAÇÕES DA LIQUIDAÇÃO")
        arquivos_nfe = obter_caminho_arquivos_modal("notas_fiscais", ano, codigo_mun)
        
        if arquivos_nfe:
            df_nfe = carregar_e_filtrar_modal(arquivos_nfe)
            if not df_nfe.empty:
                # Filtrando pela nota/empenho e pelo município correspondente
                df_nfe_filtrada = df_nfe[
                    (df_nfe['numero_empenho'].astype(str).str.strip() == num_empenho_busca) &
                    (df_nfe['codigo_municipio'].astype(str).str.strip() == cod_mun_busca)
                ]
                
                if not df_nfe_filtrada.empty:
                    # Mapeando: Data, Nota fiscal, Valor
                    df_exibir_liq = pd.DataFrame()
                    df_exibir_liq['Data'] = df_nfe_filtrada['data_liquidacao'].apply(formatar_data_modal)
                    df_exibir_liq['Nota fiscal'] = df_nfe_filtrada['numero_nota_fiscal'].astype(str)
                    df_exibir_liq['Valor'] = df_nfe_filtrada['valor_liquido'].apply(lambda x: f"R$ {formatar_moeda_modal(x)}")
                    
                    st.dataframe(df_exibir_liq, use_container_width=True, hide_index=True)
                    
                    # Quantidade e totalizadores inferiores como o layout de referência
                    total_liq = df_nfe_filtrada['valor_liquido'].sum()
                    st.markdown(
                        f"<div style='display: flex; justify-content: space-between; font-size: 0.85rem; color: #555; font-weight: bold;'>"
                        f"<span>Quantidade: {len(df_nfe_filtrada)}</span>"
                        f"<span>Valor total: R$ {formatar_moeda_modal(total_liq)}</span>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("Nenhuma movimentação de liquidação registrada para este empenho.")
            else:
                st.warning("Base de dados de notas fiscais/liquidação sem registros.")
        else:
            st.caption("Base de liquidações não localizada para este período.")

    # --- 2. Movimentações de Pagamento (Lado Direito) ---
    with col_pag:
        st.markdown("#### 💸 MOVIMENTAÇÕES DE PAGAMENTO")
        arquivos_pag = obter_caminho_arquivos_modal("notas_pagamentos", ano, codigo_mun)
        
        if arquivos_pag:
            df_pag = carregar_e_filtrar_modal(arquivos_pag)
            if not df_pag.empty:
                # Filtrando pelo empenho e município correspondente
                df_pag_filtrado = df_pag[
                    (df_pag['numero_empenho'].astype(str).str.strip() == num_empenho_busca) &
                    (df_pag['codigo_municipio'].astype(str).str.strip() == cod_mun_busca)
                ]
                
                if not df_pag_filtrado.empty:
                    # Mapeando: Data, Número pagamento, Valor
                    df_exibir_pag = pd.DataFrame()
                    df_exibir_pag['Data'] = df_pag_filtrado['data_nota_pagamento'].apply(formatar_data_modal)
                    df_exibir_pag['Número pagamento'] = df_pag_filtrado['numero_nota_pagamento'].astype(str)
                    df_exibir_pag['Valor'] = df_pag_filtrado['valor_nota_pagamento'].apply(lambda x: f"R$ {formatar_moeda_modal(x)}")
                    
                    st.dataframe(df_exibir_pag, use_container_width=True, hide_index=True)
                    
                    # Quantidade e totalizadores de pagamentos
                    total_pag = df_pag_filtrado['valor_nota_pagamento'].sum()
                    st.markdown(
                        f"<div style='display: flex; justify-content: space-between; font-size: 0.85rem; color: #555; font-weight: bold;'>"
                        f"<span>Quantidade: {len(df_pag_filtrado)}</span>"
                        f"<span>Valor total: R$ {formatar_moeda_modal(total_pag)}</span>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("Nenhuma movimentação de pagamento registrada para este empenho.")
            else:
                st.warning("Base de dados de pagamentos sem registros.")
        else:
            st.caption("Base de pagamentos não localizada para este período.")

    st.divider()
    
    # Botão de download/geração do PDF
    try:
        pdf_data = gerar_pdf_empenho(row)
        st.download_button(
            label="🖨️ Imprimir Detalhes do Empenho (PDF)",
            data=pdf_data,
            file_name=f"Empenho_{row.get('numero_empenho', 'N/A')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Erro ao gerar o relatório em PDF: {e}")