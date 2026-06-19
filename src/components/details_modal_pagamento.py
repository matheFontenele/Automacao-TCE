import streamlit as st
import pandas as pd
import glob
import re
import requests

# ==============================================================================
# FUNÇÕES AUXILIARES DO MODAL DE PAGAMENTO
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

def normalizar_valor_unico(valor):
    if pd.isna(valor) or valor is None:
        return ""
    val_str = str(valor).strip()
    val_str = re.sub(r'\.0$', '', val_str)
    val_str = re.sub(r'^0+', '', val_str)
    return val_str.strip()

@st.cache_data(show_spinner=False)
def buscar_credor_no_empenho_pai(ano, codigo_mun, codigo_orgao, numero_empenho):
    """
    Varre os arquivos de empenho para extrair o Fornecedor original (nome_negociante)
    e o histórico do empenho que originou esta nota de pagamento.
    """
    try:
        if codigo_mun == "Todos":
            arquivos = sorted(glob.glob(f"data/notas_empenho_{ano}_*.parquet") + glob.glob(f"data/notas_empenho_{ano}.parquet"))
        else:
            mensais = glob.glob(f"data/notas_empenho_{ano}_*_{codigo_mun}.parquet")
            anuais = glob.glob(f"data/notas_empenho_{ano}_{codigo_mun}.parquet")
            arquivos = sorted(mensais + anuais)
            
        if not arquivos:
            return None
            
        # Carrega estritamente o necessário para otimização de memória
        dfs = []
        colunas = ['codigo_municipio', 'codigo_orgao', 'numero_empenho', 'nome_negociante', 'descricao_historico_empenho']
        for f in arquivos:
            try:
                dfs.append(pd.read_parquet(f, columns=colunas))
            except:
                continue
                
        if not dfs:
            return None
            
        df_emp = pd.concat(dfs, ignore_index=True)
        
        # Alinha chaves de busca limpando zeros à esquerda e floats decimais
        num_emp_b = normalizar_valor_unico(numero_empenho)
        cod_org_b = normalizar_valor_unico(codigo_orgao)
        
        df_emp['num_emp_norm'] = df_emp['numero_empenho'].apply(normalizar_valor_unico)
        df_emp['cod_org_norm'] = df_emp['codigo_orgao'].apply(normalizar_valor_unico)
        
        resultado = df_emp[
            (df_emp['num_emp_norm'] == num_emp_b) & 
            (df_emp['cod_org_norm'] == cod_org_b)
        ]
        
        if not resultado.empty:
            item = resultado.iloc[0]
            return {
                "fornecedor": item.get("nome_negociante", "Não Localizado"),
                "historico_empenho": item.get("descricao_historico_empenho", "")
            }
        return None
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def buscar_nome_orgao_api(codigo_municipio: str, ano_exercicio: str, codigo_orgao: str) -> str:
    cod_mun_fmt = str(codigo_municipio).zfill(3)
    exercicio_fmt = f"{str(ano_exercicio)[:4]}00"
    cod_org_fmt = str(codigo_orgao).zfill(2)
    
    url = "https://api-dados-abertos.tce.ce.gov.br/sim/orgaos"
    params = {"codigo_municipio": cod_mun_fmt, "exercicio_orcamento": exercicio_fmt, "$format": "json"}
    
    try:
        response = requests.get(url, params=params, timeout=8)
        if response.status_code == 200:
            elementos = response.json().get("elements", [])
            for elemento in elementos:
                org_atual = str(elemento.get("codigo_orgao", "")).zfill(2)
                if org_atual == cod_org_fmt:
                    return elemento.get("nome_orgao", "").strip()
    except Exception:
        pass
    return ""

# ==============================================================================
# DIALOG (MODAL) EXPORTADO - NOTAS DE PAGAMENTO
# ==============================================================================
@st.dialog("📋 Detalhes da Nota de Pagamento", width="large")
def exibir_modal_detalhes_pagamento(row, categoria, ano, codigo_mun, id_unico=None):
    
    num_pagamento = row.get('numero_nota_pagamento', 'N/A')
    num_empenho = row.get('numero_empenho', 'N/A')
    cod_orgao = row.get('codigo_orgao', '')
    cod_municipio = row.get('codigo_municipio', codigo_mun)
    ano_exercicio = str(row.get('exercicio_orcamento', ano))[:4]
    
    # Cabeçalho Principal do Modal
    st.write(f"### Nota de Pagamento Nº {num_pagamento}")
    st.caption(f"📍 {row.get('municipio_referencia', 'Não Informado')} — Exercício Orçamentário: {ano_exercicio}")
    st.divider()

    # ==============================================================================
    # SEÇÃO 1: INFORMAÇÕES DO DESEMBOLSO (PAGAMENTO)
    # ==============================================================================
    st.markdown("#### 💸 DETALHES DO PAGAMENTO EFETUADO")
    
    col_pag1, col_pag2 = st.columns(2)
    with col_pag1:
        st.markdown(f"**Número do Pagamento:** `{num_pagamento}`")
        st.markdown(f"**Data da Movimentação:** {formatar_data_modal(row.get('data_nota_pagamento'))}")
        st.markdown(f"**Valor Pago:** `R$ {formatar_moeda_modal(row.get('valor_nota_pagamento', 0.0))}`")
        st.markdown(f"**Doc. de Caixa / Banco:** `{row.get('numero_documento_caixa', 'N/A')}`")

    with col_pag2:
        st.markdown(f"**Responsável pelo Caixa:** {row.get('nome_responsavel_pagamento', 'Não Informado')}")
        st.markdown(f"**CPF do Responsável:** `{row.get('cpf_responsavel_pagamento', 'Não Informado')}`")
        st.markdown(f"**Número do Empenho Vinculado:** `{num_empenho}`")
        st.markdown(f"**Unidade Orçamentária:** `U.O. {row.get('codigo_unidade_orcamentaria', 'N/A')}`")

    st.divider()

    # ==============================================================================
    # SEÇÃO 2: CRUZAMENTO COM EMPENHO PAI (IDENTIFICAÇÃO DO FORNECEDOR REAL)
    # ==============================================================================
    st.markdown("#### 🤝 IDENTIFICAÇÃO DO FORNECEDOR (CREDOR REAL)")
    
    with st.spinner("Realizando cruzamento reverso com a Nota de Empenho..."):
        dados_pai = buscar_credor_no_empenho_pai(ano_exercicio, cod_municipio, cod_orgao, num_empenho)
        
    if dados_pai:
        st.success(f"**Razão Social / Fornecedor:** {dados_pai['fornecedor']}")
        if dados_pai['historico_empenho']:
            st.markdown("**🎯 Objeto/Histórico Original do Empenho:**")
            st.caption(dados_pai['historico_empenho'])
    else:
        st.warning(f"**Fornecedor Primário:** Não localizado nos arquivos locais de empenho de {ano_exercicio}.")
        st.info(f"O recurso foi liquidado e despachado sob a responsabilidade de: *{row.get('nome_responsavel_pagamento', 'Não Informado')}*.")

    st.divider()

    # ==============================================================================
    # SEÇÃO 3: INFORMAÇÕES DE ESTRUTURA INSTITUCIONAL (ÓRGÃO)
    # ==============================================================================
    st.markdown("#### 🏛️ INFORMAÇÕES DO ÓRGÃO")
    
    nome_orgao_extenso = ""
    if cod_orgao and cod_municipio:
        nome_orgao_extenso = buscar_nome_orgao_api(
            codigo_municipio=cod_municipio,
            ano_exercicio=ano_exercicio,
            codigo_orgao=cod_orgao
        )
        
    col_orc1, col_orc2 = st.columns(2)
    with col_orc1:
        st.markdown(f"**Código do Órgão:** `{cod_orgao}`")
    with col_orc2:
        if nome_orgao_extenso:
            st.markdown(f"**Nome do Órgão (API TCE):** *{nome_orgao_extenso}*")
        else:
            st.markdown(f"**Nome do Órgão (API TCE):** `Não retornado pela API`")

    st.divider()

    # Link ou botão de fechamento seguro
    if st.button("Fechar Visualização", use_container_width=True):
        st.rerun()