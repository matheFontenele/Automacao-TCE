import streamlit as st
import pandas as pd
import glob
import re
import requests

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

def normalizar_serie_pandas(serie):
    """
    Normaliza uma série do Pandas para strings limpas comparáveis:
    Remove '.0', retira espaços e remove zeros à esquerda para evitar problemas de padding.
    Exemplo: "001.0" -> "1", "020" -> "20", "2024.0" -> "2024"
    """
    return (
        serie.astype(str)
        .str.strip()
        .str.replace(r'\.0$', '', regex=True) # Remove decimal .0 do float
        .str.replace(r'^0+', '', regex=True)  # Remove zeros à esquerda para alinhar tipagens
        .str.strip()
    )

def normalizar_valor_unico(valor):
    """Normaliza um único valor escalar para o mesmo formato da função acima."""
    if pd.isna(valor) or valor is None:
        return ""
    val_str = str(valor).strip()
    val_str = re.sub(r'\.0$', '', val_str)
    val_str = re.sub(r'^0+', '', val_str)
    return val_str.strip()

@st.cache_data(show_spinner=False)
def buscar_nome_orgao_api(codigo_municipio: str, ano_exercicio: str, codigo_orgao: str) -> str:
    """
    Busca o nome do órgão na API do TCE-CE com base no código do município,
    exercício (ano) e código do órgão, aplicando normalização segura de caracteres.
    """
    # Garante o preenchimento de zeros (ex: "63" -> "063")
    cod_mun_fmt = str(codigo_municipio).zfill(3)
    # Formata o exercício do orçamento como string no formato YYYY00 (ex: "2025" -> "202500")
    exercicio_fmt = f"{str(ano_exercicio)[:4]}00"
    # Normaliza o órgão de busca (ex: 1 -> "01")
    cod_org_fmt = str(codigo_orgao).zfill(2)
    
    url = "https://api-dados-abertos.tce.ce.gov.br/sim/orgaos"
    params = {
        "codigo_municipio": cod_mun_fmt,
        "exercicio_orcamento": exercicio_fmt,
        "$format": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=8)
        if response.status_code == 200:
            dados = response.json()
            elementos = dados.get("elements", [])
            
            for elemento in elementos:
                # Compara os códigos de órgão de forma normalizada
                org_atual = str(elemento.get("codigo_orgao", "")).zfill(2)
                if org_atual == cod_org_fmt:
                    return elemento.get("nome_orgao", "").strip()
    except Exception:
        pass
    
    return ""


# ==============================================================================
# DIALOG (MODAL) EXPORTADO
# ==============================================================================
@st.dialog("📋 Detalhes do Empenho", width="large")
def exibir_modal_detalhes(row, categoria, ano, codigo_mun, id_unico=None):
    
    # --------------------------------------------------------------------------
    # 1. MAPEAMENTO SEGURO DA CHAVE COMPOSTA DE UNICIDADE DO EMPENHO
    # --------------------------------------------------------------------------
    num_empenho_busca = normalizar_valor_unico(row.get('numero_empenho'))
    cod_mun_busca     = normalizar_valor_unico(row.get('codigo_municipio'))
    cod_orgao_busca   = normalizar_valor_unico(row.get('codigo_orgao'))
    cod_unid_busca    = normalizar_valor_unico(row.get('codigo_unidade_orcamentaria'))
    
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
        

    st.divider()

    # ==============================================================================
    # SEÇÃO 2: INFORMAÇÕES DE ORÇAMENTO
    # ==============================================================================
    st.markdown("#### 🏛️ INFORMAÇÕES DE ORÇAMENTO")
    
    # Busca dinâmica do nome do órgão usando a API do TCE-CE
    cod_orgao_bruto = row.get('codigo_orgao', '')
    cod_municipio_bruto = row.get('codigo_municipio', codigo_mun)
    ano_exercicio = str(row.get('exercicio_orcamento', ano))[:4]
    
    nome_orgao_extenso = ""
    if cod_orgao_bruto and cod_municipio_bruto:
        nome_orgao_extenso = buscar_nome_orgao_api(
            codigo_municipio=cod_municipio_bruto,
            ano_exercicio=ano_exercicio,
            codigo_orgao=cod_orgao_bruto
        )
    
    col_orc1, col_orc2 = st.columns(2)
    with col_orc1:
        unidade_gestora = f"{row.get('municipio_referencia', 'N/A')} - U.O. {row.get('codigo_unidade_orcamentaria', 'N/A')}"
        st.markdown(f"**Unidade Gestora:** {unidade_gestora}")

    with col_orc2:
        # Mostra o código e o nome retornado pela API (caso exista)
        if nome_orgao_extenso:
            st.markdown(f"**Órgão:** `{cod_orgao_bruto}` — *{nome_orgao_extenso}*")
        else:
            st.markdown(f"**Órgão:** `{cod_orgao_bruto or 'N/A'}`")

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
        arquivos_liq = obter_caminho_arquivos_modal("liquidacoes", ano, codigo_mun)
        
        if arquivos_liq:
            df_liq = carregar_e_filtrar_modal(arquivos_liq)
            if not df_liq.empty:
                # Normalização segura das chaves na base de Notas Fiscais
                df_liq['num_emp_norm'] = normalizar_serie_pandas(df_liq['numero_empenho'])
                df_liq['cod_mun_norm'] = normalizar_serie_pandas(df_liq['codigo_municipio'])
                df_liq['cod_org_norm'] = normalizar_serie_pandas(df_liq['codigo_orgao'])

                # Filtro de liquidações aplicando as chaves normalizadas (Numero de empenho + Codigo de municio + Código de órgão)
                df_liq_filtrada = df_liq[
                    (df_liq['num_emp_norm'] == num_empenho_busca) &
                    (df_liq['cod_mun_norm'] == cod_mun_busca) &
                    (df_liq['cod_org_norm'] == cod_orgao_busca)
                ]
                
                if not df_liq_filtrada.empty:
                    df_exibir_liq = pd.DataFrame()

                    # 1. Identifica e formata a data da liquidação dinamicamente
                    if 'data_nota_liquidacao' in df_liq_filtrada.columns:
                        col_data_liq = 'data_nota_liquidacao'
                    elif 'data_liquidacao' in df_liq_filtrada.columns:
                        col_data_liq = 'data_liquidacao'
                    elif 'data_emissao' in df_liq_filtrada.columns:
                        col_data_liq = 'data_emissao'
                    else:
                        col_data_liq = None

                    if col_data_liq:
                        df_exibir_liq['Data'] = df_liq_filtrada[col_data_liq].apply(formatar_data_modal)
                    else:
                        df_exibir_liq['Data'] = "Não informada"
                    
                    # 2. 🛡️ FIX KEYERROR: Identifica o número do documento de liquidação de forma resiliente
                    if 'numero_nota_liquidacao' in df_liq_filtrada.columns:
                        col_num_liq = 'numero_nota_liquidacao'
                    elif 'numero_nota_fiscal' in df_liq_filtrada.columns:
                        col_num_liq = 'numero_nota_fiscal'
                    elif 'numero_documento' in df_liq_filtrada.columns:
                        col_num_liq = 'numero_documento'
                    else:
                        col_num_liq = None

                    if col_num_liq:
                        df_exibir_liq['Nº Liquidação'] = df_liq_filtrada[col_num_liq].astype(str)
                    else:
                        # Fallback amigável: se não achar o documento da liq, exibe o do empenho original
                        df_exibir_liq['Nº Liquidação'] = df_liq_filtrada['numero_empenho'].astype(str)
                    
                    # 3. Identifica e calcula o valor bruto/líquido liquidado
                    if 'valor_bruto_nota_liquidacao' in df_liq_filtrada.columns:
                        col_valor_liq = 'valor_bruto_nota_liquidacao'
                    elif 'valor_liquidado' in df_liq_filtrada.columns:
                        col_valor_liq = 'valor_liquidado'
                    elif 'valor_bruto' in df_liq_filtrada.columns:
                        col_valor_liq = 'valor_bruto'
                    elif 'valor_nota_fiscal' in df_liq_filtrada.columns:
                        col_valor_liq = 'valor_nota_fiscal'
                    else:
                        col_valor_liq = None

                    if col_valor_liq:
                        df_exibir_liq['Valor'] = df_liq_filtrada[col_valor_liq].apply(lambda x: f"R$ {formatar_moeda_modal(x)}")
                        total_liq = df_liq_filtrada[col_valor_liq].sum()
                    else:
                        df_exibir_liq['Valor'] = "R$ 0,00"
                        total_liq = 0.0
                    
                    st.dataframe(df_exibir_liq, use_container_width=True, hide_index=True)
                    
                    st.markdown(
                        f"<div style='display: flex; justify-content: space-between; font-size: 0.85rem; color: #555; font-weight: bold;'>"
                        f"<span>Quantidade: {len(df_liq_filtrada)}</span>"
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
                # Normalização segura das chaves na base de Notas de Pagamento
                df_pag['num_emp_norm'] = normalizar_serie_pandas(df_pag['numero_empenho'])
                df_pag['cod_mun_norm'] = normalizar_serie_pandas(df_pag['codigo_municipio'])
                df_pag['cod_org_norm'] = normalizar_serie_pandas(df_pag['codigo_orgao'])
                
                if 'codigo_unidade_orcamentaria' in df_pag.columns:
                    df_pag['cod_uni_norm'] = normalizar_serie_pandas(df_pag['codigo_unidade_orcamentaria'])
                    condicao_unidade_pg = (df_pag['cod_uni_norm'] == cod_unid_busca)
                else:
                    condicao_unidade_pg = True

                # Aplicação do Filtro Consistente
                df_pag_filtrado = df_pag[
                    (df_pag['num_emp_norm'] == num_empenho_busca) &
                    (df_pag['cod_mun_norm'] == cod_mun_busca) &
                    (df_pag['cod_org_norm'] == cod_orgao_busca) &
                    condicao_unidade_pg
                ]
                
                if not df_pag_filtrado.empty:
                    df_exibir_pag = pd.DataFrame()
                    df_exibir_pag['Data'] = df_pag_filtrado['data_nota_pagamento'].apply(formatar_data_modal)
                    df_exibir_pag['Número pagamento'] = df_pag_filtrado['numero_nota_pagamento'].astype(str)
                    
                    col_valor_pag = 'valor_nota_pagamento' if 'valor_nota_pagamento' in df_pag_filtrado.columns else 'valor_pago'
                    df_exibir_pag['Valor'] = df_pag_filtrado[col_valor_pag].apply(lambda x: f"R$ {formatar_moeda_modal(x)}")
                    
                    st.dataframe(df_exibir_pag, use_container_width=True, hide_index=True)
                    
                    total_pag = df_pag_filtrado[col_valor_pag].sum()
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
        enviar_liq = df_liq_filtrada if ('df_liq_filtrada' in locals() and df_liq_filtrada is not None and not df_liq_filtrada.empty) else None
        enviar_pag = df_pag_filtrado if ('df_pag_filtrado' in locals() and df_pag_filtrado is not None and not df_pag_filtrado.empty) else None
        
        # Gera o PDF injetando os dados já higienizados e filtrados
        pdf_data = gerar_pdf_empenho(row, df_liq_filtrada=enviar_liq, df_pag_filtrado=enviar_pag)
        
        st.download_button(
            label="🖨️ Imprimir Detalhes do Empenho Completo (PDF)",
            data=pdf_data,
            file_name=f"Empenho_{row.get('numero_empenho', 'N/A')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Erro ao gerar o relatório em PDF: {e}")