import streamlit as st
import pandas as pd
import glob
import re
import requests
from datetime import datetime

# IMPORTANDO O GERADOR DE PDF ISOLADO
from modules.gerador_pdf import gerar_pdf_empenho

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
        # Tenta converter se for timestamp
        if isinstance(data_raw, (datetime, pd.Timestamp)):
            return data_raw.strftime('%d/%m/%Y')
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
        except Exception as e:
            st.warning(f"Erro ao carregar arquivo {f}: {e}")
            continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def normalizar_chave(valor):
    """
    Normaliza um valor para comparação segura.
    Remove apenas .0 final e espaços, mantendo zeros à esquerda.
    """
    if pd.isna(valor) or valor is None:
        return ""
    val_str = str(valor).strip()
    val_str = re.sub(r'\.0$', '', val_str)
    return val_str

def criar_variacoes_empenho(num_empenho):
    """
    Cria múltiplas variações do número de empenho para busca flexível.
    Ex: "02120033" -> ["02120033", "2120033"]
    """
    if not num_empenho:
        return [""]
    
    # Remove .0 se existir
    num_limpo = re.sub(r'\.0$', '', str(num_empenho).strip())
    
    variacoes = [num_limpo]  # Original
    
    # Versão sem zeros à esquerda
    sem_zeros = num_limpo.lstrip('0') or '0'
    if sem_zeros != num_limpo:
        variacoes.append(sem_zeros)
    
    # Versão com zeros à esquerda (8 dígitos)
    com_zeros = num_limpo.zfill(8)
    if com_zeros != num_limpo:
        variacoes.append(com_zeros)
    
    return variacoes

@st.cache_data(show_spinner=False)
def buscar_nome_orgao_api(codigo_municipio: str, ano_exercicio: str, codigo_orgao: str) -> str:
    """Busca o nome do órgão na API do TCE-CE."""
    cod_mun_fmt = str(codigo_municipio).zfill(3)
    exercicio_fmt = f"{str(ano_exercicio)[:4]}00"
    cod_org_fmt = str(codigo_orgao).zfill(2)
    
    url = "https://api-dados-abertos.tce.ce.gov.br/sim/orgaos"
    params = {
        "codigo_municipio": cod_mun_fmt,
        "exercicio_orcamento": exercicio_fmt,
        "$format": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            elementos = dados.get("elements", [])
            
            for elemento in elementos:
                org_atual = str(elemento.get("codigo_orgao", "")).zfill(2)
                if org_atual == cod_org_fmt:
                    return elemento.get("nome_orgao", "").strip()
    except Exception:
        pass
    
    return ""


# ==============================================================================
# DIALOG (MODAL) EXPORTADO - LAYOUT ANTIGO COM MELHORIAS
# ==============================================================================
@st.dialog("📋 Detalhes do Empenho", width="large")
def exibir_modal_detalhes(row, categoria, ano, codigo_mun, id_unico=None):
    
    # ==============================================================================
    # 1. PREPARAÇÃO DAS CHAVES DE BUSCA
    # ==============================================================================
    num_empenho = str(row.get('numero_empenho', '')).strip()
    cod_municipio = str(row.get('codigo_municipio', '')).strip()
    cod_orgao = str(row.get('codigo_orgao', '')).strip()
    cod_unidade = str(row.get('codigo_unidade_orcamentaria', '')).strip()
    
    # Cabeçalho Principal do Modal
    st.write(f"### Empenho Nº {num_empenho}")
    municipio_nome = row.get('municipio_referencia', 'Não Informado')
    exercicio = str(row.get('exercicio_orcamento', ano))[:4]
    st.caption(f"📍 {municipio_nome} — Exercício: {exercicio}")
    st.divider()

    # ==============================================================================
    # SEÇÃO 1: INFORMAÇÕES BÁSICAS DO EMPENHO
    # ==============================================================================
    st.markdown("#### 📄 Informações do Empenho")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Número:** `{num_empenho}`")
        data_emissao = row.get('data_emissao_empenho', 'Não informada')
        st.markdown(f"**Data:** {formatar_data_modal(data_emissao)}")
        valor_empenho = row.get('valor_empenhado', 0.0)
        st.markdown(f"**Valor:** R$ {formatar_moeda_modal(valor_empenho)}")

    with col2:
        fornecedor = row.get('nome_negociante', 'Não Informado')
        st.markdown(f"**Fornecedor:** {fornecedor}")
        cnpj = row.get('numero_documento_negociante', 'Ocultado')
        st.markdown(f"**CNPJ/CPF:** `{cnpj}`")
        
    st.divider()

    # ==============================================================================
    # SEÇÃO 2: INFORMAÇÕES DE ORÇAMENTO
    # ==============================================================================
    st.markdown("#### 🏛️ Informações de Orçamento")
    
    # Busca nome do órgão via API
    nome_orgao = ""
    if cod_orgao and cod_municipio:
        nome_orgao = buscar_nome_orgao_api(cod_municipio, exercicio, cod_orgao)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Unidade Gestora:** {municipio_nome} - U.O. {cod_unidade}")
    with col2:
        if nome_orgao:
            st.markdown(f"**Órgão:** `{cod_orgao}` — {nome_orgao}")
        else:
            st.markdown(f"**Órgão:** `{cod_orgao}`")

    st.divider()

    # ==============================================================================
    # SEÇÃO 3: HISTÓRICO / DESCRIÇÃO
    # ==============================================================================
    st.markdown("#### 📜 Histórico / Descrição")
    historico = row.get('descricao_historico_empenho', 'Sem descrição.')
    st.info(historico)

    st.divider()

    # ==============================================================================
    # SEÇÃO 4: MOVIMENTAÇÕES (LADO A LADO)
    # ==============================================================================
    st.markdown("##### 📊 Movimentações")
    col_liq, col_pag = st.columns(2)

    # --- MOVIMENTAÇÕES DA LIQUIDAÇÃO ---
    with col_liq:
        st.markdown("**🔍 MOVIMENTAÇÕES DA LIQUIDAÇÃO**")
        
        try:
            arquivos_liq = obter_caminho_arquivos_modal("liquidacoes", ano, codigo_mun)
            
            if not arquivos_liq:
                st.warning("⚠️ Nenhum arquivo de liquidação encontrado para este período.")
                df_liq_filtrada = pd.DataFrame()
                total_liq = 0.0
            else:
                df_liq = carregar_e_filtrar_modal(arquivos_liq)
                
                if df_liq.empty:
                    st.warning("⚠️ Base de liquidações vazia.")
                    df_liq_filtrada = pd.DataFrame()
                    total_liq = 0.0
                else:
                    # Normaliza colunas de chave
                    df_liq['num_emp_norm'] = df_liq['numero_empenho'].apply(normalizar_chave)
                    df_liq['cod_mun_norm'] = df_liq['codigo_municipio'].apply(normalizar_chave)
                    df_liq['cod_org_norm'] = df_liq['codigo_orgao'].apply(normalizar_chave)
                    
                    # Normaliza chaves de busca
                    num_emp_variacoes = criar_variacoes_empenho(num_empenho)
                    cod_mun_norm = normalizar_chave(cod_municipio)
                    cod_org_norm = normalizar_chave(cod_orgao)

                    # Filtra com variações do número de empenho
                    df_liq_filtrada = df_liq[
                        (df_liq['num_emp_norm'].isin(num_emp_variacoes)) &
                        (df_liq['cod_mun_norm'] == cod_mun_norm) &
                        (df_liq['cod_org_norm'] == cod_org_norm)
                    ].copy()
                    
                    if df_liq_filtrada.empty:
                        st.warning(f"⚠️ Nenhuma liquidação encontrada para o empenho {num_empenho}.")
                        total_liq = 0.0
                    else:
                        # Prepara DataFrame para exibição
                        df_exibir = pd.DataFrame()
                        
                        # Data
                        if 'data_nota_liquidacao' in df_liq_filtrada.columns:
                            df_exibir['Data'] = df_liq_filtrada['data_nota_liquidacao'].apply(formatar_data_modal)
                        elif 'data_liquidacao' in df_liq_filtrada.columns:
                            df_exibir['Data'] = df_liq_filtrada['data_liquidacao'].apply(formatar_data_modal)
                        elif 'data_emissao' in df_liq_filtrada.columns:
                            df_exibir['Data'] = df_liq_filtrada['data_emissao'].apply(formatar_data_modal)
                        else:
                            df_exibir['Data'] = "N/A"
                        
                        # Número
                        if 'numero_nota_liquidacao' in df_liq_filtrada.columns:
                            df_exibir['Nº Liquidação'] = df_liq_filtrada['numero_nota_liquidacao'].astype(str)
                        elif 'numero_nota_fiscal' in df_liq_filtrada.columns:
                            df_exibir['Nº Liquidação'] = df_liq_filtrada['numero_nota_fiscal'].astype(str)
                        elif 'numero_documento' in df_liq_filtrada.columns:
                            df_exibir['Nº Liquidação'] = df_liq_filtrada['numero_documento'].astype(str)
                        else:
                            df_exibir['Nº Liquidação'] = num_empenho
                        
                        # Valor
                        col_valor = None
                        for col in ['valor_bruto_nota_liquidacao', 'valor_liquidado', 'valor_bruto', 'valor_nota_fiscal']:
                            if col in df_liq_filtrada.columns:
                                col_valor = col
                                break
                        
                        if col_valor:
                            df_liq_filtrada['valor_num'] = pd.to_numeric(df_liq_filtrada[col_valor], errors='coerce').fillna(0)
                            df_exibir['Valor'] = df_liq_filtrada['valor_num'].apply(lambda x: f"R$ {formatar_moeda_modal(x)}")
                            total_liq = df_liq_filtrada['valor_num'].sum()
                        else:
                            df_exibir['Valor'] = "R$ 0,00"
                            total_liq = 0.0
                        
                        # Exibe tabela
                        st.dataframe(df_exibir, use_container_width=True, hide_index=True)
                        
                        # Resumo
                        st.markdown(
                            f"<div style='font-size: 0.85rem; color: #888; margin-top: 8px;'>"
                            f"Quantidade: <b>{len(df_liq_filtrada)}</b> | "
                            f"Valor total: <b>R$ {formatar_moeda_modal(total_liq)}</b>"
                            f"</div>", 
                            unsafe_allow_html=True
                        )
                        
        except Exception as e:
            st.error(f"❌ Erro ao carregar liquidações: {str(e)}")
            df_liq_filtrada = pd.DataFrame()
            total_liq = 0.0

    # --- MOVIMENTAÇÕES DE PAGAMENTO ---
    with col_pag:
        st.markdown("**💸 MOVIMENTAÇÕES DE PAGAMENTO**")
        
        try:
            arquivos_pag = obter_caminho_arquivos_modal("notas_pagamentos", ano, codigo_mun)
            
            if not arquivos_pag:
                st.warning("⚠️ Nenhum arquivo de pagamento encontrado para este período.")
                df_pag_filtrado = pd.DataFrame()
                total_pag = 0.0
            else:
                df_pag = carregar_e_filtrar_modal(arquivos_pag)
                
                if df_pag.empty:
                    st.warning("⚠️ Base de pagamentos vazia.")
                    df_pag_filtrado = pd.DataFrame()
                    total_pag = 0.0
                else:
                    # Normaliza colunas de chave
                    df_pag['num_emp_norm'] = df_pag['numero_empenho'].apply(normalizar_chave)
                    df_pag['cod_mun_norm'] = df_pag['codigo_municipio'].apply(normalizar_chave)
                    df_pag['cod_org_norm'] = df_pag['codigo_orgao'].apply(normalizar_chave)
                    
                    if 'codigo_unidade_orcamentaria' in df_pag.columns:
                        df_pag['cod_uni_norm'] = df_pag['codigo_unidade_orcamentaria'].apply(normalizar_chave)
                        cod_uni_norm = normalizar_chave(cod_unidade)
                        filtro_unidade = (df_pag['cod_uni_norm'] == cod_uni_norm)
                    else:
                        filtro_unidade = True
                    
                    # Filtra
                    num_emp_variacoes = criar_variacoes_empenho(num_empenho)

                    # Filtra com variações
                    df_pag_filtrado = df_pag[
                        (df_pag['num_emp_norm'].isin(num_emp_variacoes)) &
                        (df_pag['cod_mun_norm'] == cod_mun_norm) &
                        (df_pag['cod_org_norm'] == cod_org_norm) &
                        filtro_unidade
                    ].copy()
                    
                    if df_pag_filtrado.empty:
                        st.warning(f"⚠️ Nenhum pagamento encontrado para o empenho {num_empenho}.")
                        total_pag = 0.0
                    else:
                        # Prepara DataFrame para exibição
                        df_exibir = pd.DataFrame()
                        
                        # Data
                        if 'data_nota_pagamento' in df_pag_filtrado.columns:
                            df_exibir['Data'] = df_pag_filtrado['data_nota_pagamento'].apply(formatar_data_modal)
                        else:
                            df_exibir['Data'] = "N/A"
                        
                        # Número
                        if 'numero_nota_pagamento' in df_pag_filtrado.columns:
                            df_exibir['Número pagamento'] = df_pag_filtrado['numero_nota_pagamento'].astype(str)
                        else:
                            df_exibir['Número pagamento'] = "N/A"
                        
                        # Valor
                        col_valor = 'valor_nota_pagamento' if 'valor_nota_pagamento' in df_pag_filtrado.columns else 'valor_pago'
                        
                        if col_valor in df_pag_filtrado.columns:
                            df_pag_filtrado['valor_num'] = pd.to_numeric(df_pag_filtrado[col_valor], errors='coerce').fillna(0)
                            df_exibir['Valor'] = df_pag_filtrado['valor_num'].apply(lambda x: f"R$ {formatar_moeda_modal(x)}")
                            total_pag = df_pag_filtrado['valor_num'].sum()
                        else:
                            df_exibir['Valor'] = "R$ 0,00"
                            total_pag = 0.0
                        
                        # Exibe tabela
                        st.dataframe(df_exibir, use_container_width=True, hide_index=True)
                        
                        # Resumo
                        st.markdown(
                            f"<div style='font-size: 0.85rem; color: #888; margin-top: 8px;'>"
                            f"Quantidade: <b>{len(df_pag_filtrado)}</b> | "
                            f"Valor total: <b>R$ {formatar_moeda_modal(total_pag)}</b>"
                            f"</div>", 
                            unsafe_allow_html=True
                        )
                        
        except Exception as e:
            st.error(f"❌ Erro ao carregar pagamentos: {str(e)}")
            df_pag_filtrado = pd.DataFrame()
            total_pag = 0.0

    st.divider()
    
    # ==============================================================================
    # BOTÃO PDF
    # ==============================================================================
    try:
        enviar_liq = df_liq_filtrada if not df_liq_filtrada.empty else None
        enviar_pag = df_pag_filtrado if not df_pag_filtrado.empty else None
        
        pdf_data = gerar_pdf_empenho(row, df_liq_filtrada=enviar_liq, df_pag_filtrado=enviar_pag)
        
        st.download_button(
            label="🖨️ Imprimir Detalhes do Empenho Completo (PDF)",
            data=pdf_data,
            file_name=f"Empenho_{num_empenho}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"❌ Erro ao gerar PDF: {str(e)}")