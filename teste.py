import streamlit as st
import pandas as pd
import glob
import re
import datetime
from src.extraction import carregar_municipios
from src.details_modal import exibir_modal_detalhes
from src.details_modal_pagamento import exibir_modal_detalhes_pagamento
from src.exportadores import renderizar_botoes_exportacao
from src.details_modal import obter_caminho_arquivos_modal, carregar_e_filtrar_modal

# ==============================================================================
# CSS DOS CARDS (Otimizado e idêntico ao padrão visual do TCE)
# ==============================================================================
CSS_CARDS = """
<style>
    .report-card {
        background-color: #FFFFFF;
        border: 1px solid rgba(0, 0, 0, 0.1); 
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px; 
        border-left: 8px solid #ff4b4b;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        color: #1E1E24 !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .report-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
    }

    .card-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }

    .card-header { 
        color: #64748b; 
        font-weight: 700; 
        font-size: 0.8rem; 
        text-transform: uppercase; 
        letter-spacing: 0.5px; 
    }

    .match-badge {
        background-color: #fef08a;
        color: #854d0e;
        font-size: 0.7rem;
        font-weight: bold;
        padding: 2px 8px;
        border-radius: 20px;
        border: 1px solid #fef08a;
        text-transform: uppercase;
    }

    .status-badge {
        font-size: 0.7rem;
        font-weight: bold;
        padding: 2px 10px;
        border-radius: 20px;
        text-transform: uppercase;
        margin-left: 8px;
    }
    .status-pago { background-color: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .status-parcial { background-color: #fef9c3; color: #a16207; border: 1px solid #fef08a; }
    .status-pendente { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }

    .card-vendor { 
        font-size: 1.2rem; 
        font-weight: 800; 
        color: #0f172a; 
        margin: 6px 0; 
    }
    
    .card-meta-row {
        display: flex;
        gap: 16px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 12px;
    }

    .card-org { 
        color: #ff4b4b; 
    }

    .card-date {
        color: #64748b;
    }

    .values-grid {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-top: 16px;
    }
    
    .value-col {
        flex: 1;
        background: #f8fafc;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    
    .value-title {
        font-size: 0.7rem;
        color: #64748b;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    
    .value-num {
        font-family: 'Roboto Mono', monospace;
        font-weight: 800;
        font-size: 1.2rem;
    }
    
    .val-empenhado { color: #0f172a; }
    .val-liquidado { color: #2563eb; }
    .val-pago { color: #16a34a; }

    mark {
        background-color: #fef08a !important;
        color: #000000 !important;
        font-weight: bold;
        padding: 0 2px;
        border-radius: 3px;
    }
</style>
"""

# ==============================================================================
# FUNÇÕES DE TRATAMENTO E CARREGAMENTO DE DADOS (Consulta Geral)
# ==============================================================================
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

def formatar_moeda(valor):
    try:
        if pd.isna(valor) or valor is None:
            return "0,00"
        val_float = float(valor)
        return f"{val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

def formatar_data(data_raw):
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

def obter_caminho_arquivos(prefixo, ano, codigo_mun):
    if codigo_mun == "Todos":
        return sorted(glob.glob(f"data/{prefixo}_{ano}_*.parquet") + glob.glob(f"data/{prefixo}_{ano}.parquet"))
    
    mensais = glob.glob(f"data/{prefixo}_{ano}_*_{codigo_mun}.parquet")
    anuais = glob.glob(f"data/{prefixo}_{ano}_{codigo_mun}.parquet")
    return sorted(mensais + anuais)


# ==============================================================================
# RENDERIZADOR DA PÁGINA
# ==============================================================================
def render_consultation_page():
    st.header("🔍 Consulta Detalhada")
    st.markdown(CSS_CARDS, unsafe_allow_html=True)

    if "consulta_realizada" not in st.session_state:
        st.session_state.consulta_realizada = False
    if "df_resultado" not in st.session_state:
        st.session_state.df_resultado = pd.DataFrame()
    if "filtros_aplicados" not in st.session_state:
        st.session_state.filtros_aplicados = {}

    lista_municipios = carregar_municipios()
    opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}

    with st.expander("Opções de Filtro", expanded=not st.session_state.consulta_realizada):
        
        # --- LINHA 1: Tipo de Documento (70%) e Município (30%) ---
        col1, col2 = st.columns([7, 3])
        with col1:
            categoria_sel = st.selectbox(
                "Tipo de Documento", 
                ["Notas de Empenho", "Notas Fiscais", "Itens de Notas Fiscais", "Notas de Pagamento", "Liquidações"]
            )
        with col2:
            municipio_sel = st.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
        
        # --- LINHA 2: Filtro de Pagamento (34%) + Data Inicial (33%) + Data Final (33%) ---
        col3, col4, col5 = st.columns([34, 33, 33])
        with col3:
            # O filtro de pagamento só faz sentido para Notas de Empenho nesta regra de negócio
            desabilitar_pagamento = (categoria_sel != "Notas de Empenho")
            pagamento_sel = st.selectbox(
                "Filtro de Pagamento", 
                ["TODOS", "PENDENTE", "PARCIAL", "PAGO"],
                disabled=desabilitar_pagamento
            )
            if desabilitar_pagamento:
                pagamento_sel = "TODOS"
                
        with col4:
            ano_atual = datetime.date.today().year
            data_inicial = st.date_input(
                "Data Inicial", 
                value=datetime.date(ano_atual, 1, 1), 
                format="DD/MM/YYYY"
            )
        with col5:
            data_final = st.date_input(
                "Data Final", 
                value=datetime.date(ano_atual, 12, 31), 
                format="DD/MM/YYYY"
            )

        # --- LINHA 3: Múltiplos Fornecedores (100%) ---
        fornecedores_filtro = st.text_input(
            "Fornecedores / Credores (Múltiplos separados por vírgula)", 
            placeholder="Ex: Nome Credor, 12.345.678/0001-90, Outra Razão Social...",
            help="Você pode digitar partes do nome ou CNPJs/CPFs inteiros separados por vírgula."
        ).strip()
        
        # --- LINHA 4: Busca Geral (82%) e Botão Consultar (18%) ---
        col_busca, col_botao = st.columns([82, 18])
        with col_busca:
            filtro_geral = st.text_input(
                "Busca Geral", 
                placeholder="Digite nº empenho, credor, CNPJ, responsável, item ou conteúdo do histórico...",
                label_visibility="visible"
            ).strip()
        
        with col_botao:
            col_botao.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
            btn_consultar = col_botao.button("Consultar", use_container_width=True, type="primary")

    if btn_consultar:
        mapa_prefixos = {
            "Notas de Empenho": "notas_empenho",
            "Notas Fiscais": "notas_fiscais",
            "Itens de Notas Fiscais": "itens_notas_fiscais",
            "Notas de Pagamento": "notas_pagamentos",
            "Liquidações": "liquidacoes"
        }

        prefixo = mapa_prefixos[categoria_sel]
        codigo_mun_busca = "Todos"
        if municipio_sel != "Todos":
            codigo_mun_busca = opcoes_mun[municipio_sel]['codigo_municipio']

        # Descobre a lista de anos a buscar com base no intervalo digitado nas datas
        anos_busca = list(range(data_inicial.year, data_final.year + 1))

        # Reúne os arquivos de todos os anos contidos no range
        arquivos = []
        for ano in anos_busca:
            arquivos.extend(obter_caminho_arquivos(prefixo, ano, codigo_mun_busca))

        if arquivos:
            df = carregar_e_filtrar(arquivos)

            if municipio_sel != "Todos" and not df.empty and 'municipio_referencia' in df.columns:
                nome_municipio_real = opcoes_mun[municipio_sel]['nome_municipio']
                df = df[df['municipio_referencia'].str.upper() == nome_municipio_real.upper()]

            if not df.empty:
                df['match_reason'] = "" 

                if categoria_sel == "Notas de Empenho":
                    df['codigo_municipio'] = df['codigo_municipio'].astype(str)
                    df['codigo_orgao'] = df['codigo_orgao'].astype(str)
                    df['numero_empenho'] = df['numero_empenho'].astype(str)
                    df['chave_composta'] = df['codigo_municipio'].str.strip() + "_" + df['codigo_orgao'].str.strip() + "_" + df['numero_empenho'].str.strip()
                    
                    # --- NOVA LÓGICA DE AGREGAÇÃO DO LIQUIDADO POR RANGE DE ANOS ---
                    arq_liq = []
                    for ano in anos_busca:
                        arq_liq.extend(obter_caminho_arquivos("liquidacoes", ano, codigo_mun_busca))
                    df_liq = carregar_e_filtrar(arq_liq)
                    liq_map = {}

                    if not df_liq.empty:
                        df_liq['codigo_municipio'] = df_liq['codigo_municipio'].astype(str)
                        df_liq['codigo_orgao'] = df_liq['codigo_orgao'].astype(str)
                        df_liq['numero_empenho'] = df_liq['numero_empenho'].astype(str)
                        df_liq['chave_composta'] = df_liq['codigo_municipio'].str.strip() + "_" + df_liq['codigo_orgao'].str.strip() + "_" + df_liq['numero_empenho'].str.strip()
                        
                        if 'valor_bruto_nota_liquidacao' in df_liq.columns:
                            col_valor_liq = 'valor_bruto_nota_liquidacao'
                        elif 'valor_liquidado' in df_liq.columns:
                            col_valor_liq = 'valor_liquidado'
                        elif 'valor_bruto' in df_liq.columns:
                            col_valor_liq = 'valor_bruto'
                        else:
                            col_valor_liq = None
                            
                        if col_valor_liq:
                            df_liq[col_valor_liq] = pd.to_numeric(df_liq[col_valor_liq], errors='coerce').fillna(0.0)
                            liq_map = df_liq.groupby('chave_composta')[col_valor_liq].sum().to_dict()
                    
                    # --- AGREGAÇÃO DO PAGO POR RANGE DE ANOS ---
                    arq_pg = []
                    for ano in anos_busca:
                        arq_pg.extend(obter_caminho_arquivos("notas_pagamentos", ano, codigo_mun_busca))
                    df_pg = carregar_e_filtrar(arq_pg)
                    pag_map = {}
                   
                    if not df_pg.empty:
                        df_pg['codigo_municipio'] = df_pg['codigo_municipio'].astype(str)
                        df_pg['codigo_orgao'] = df_pg['codigo_orgao'].astype(str)
                        df_pg['numero_empenho'] = df_pg['numero_empenho'].astype(str)
                        df_pg['chave_composta'] = df_pg['codigo_municipio'].str.strip() + "_" + df_pg['codigo_orgao'].str.strip() + "_" + df_pg['numero_empenho'].str.strip()
                        
                        df_pg['valor_nota_pagamento'] = pd.to_numeric(df_pg['valor_nota_pagamento'], errors='coerce').fillna(0.0)
                        pag_map = df_pg.groupby('chave_composta')['valor_nota_pagamento'].sum().to_dict()
                   
                    df['valor_liquidado'] = df['chave_composta'].map(liq_map).fillna(0.0)
                    df['valor_pago'] = df['chave_composta'].map(pag_map).fillna(0.0)

                    def calcular_status_pagamento(row):
                        emp = float(row.get('valor_empenhado', 0.0))
                        pag = float(row.get('valor_pago', 0.0))
                        if pag <= 0.0:
                            return "PENDENTE"
                        elif pag >= emp:
                            return "PAGO"
                        else:
                            return "PARCIAL"

                    df['status_pagamento'] = df.apply(calcular_status_pagamento, axis=1)

                    if pagamento_sel != "TODOS":
                        df = df[df['status_pagamento'] == pagamento_sel]

                # ==============================================================
                # 🌟 APLICANDO O FILTRO 1: INTERVALO DE DATAS NATIVO
                # ==============================================================
                if data_inicial and data_final:
                    col_data_map = {
                        "Notas de Empenho": "data_emissao_empenho",
                        "Notas de Pagamento": "data_nota_pagamento",
                        "Itens de Notas Fiscais": "data_emissao",
                        "Notas Fiscais": "data_emissao"
                    }
                    col_data_efetiva = col_data_map.get(categoria_sel)
                    
                    if categoria_sel == "Liquidações":
                        for c_dt in ['data_nota_liquidacao', 'data_liquidacao', 'data_emissao']:
                            if c_dt in df.columns:
                                col_data_efetiva = c_dt
                                break
                                
                    if col_data_efetiva and col_data_efetiva in df.columns:
                        df_dt_serie = pd.to_datetime(df[col_data_efetiva], errors='coerce').dt.date
                        df = df[(df_dt_serie >= data_inicial) & (df_dt_serie <= data_final)]

                # ==============================================================
                # 🌟 APLICANDO O FILTRO 2: MÚLTIPLOS FORNECEDORES
                # ==============================================================
                if fornecedores_filtro and not df.empty:
                    termos_forn = [t.strip().lower() for t in fornecedores_filtro.split(",") if t.strip()]
                    if termos_forn:
                        cols_fornecedor = ['nome_negociante', 'numero_documento_negociante', 'nome_responsavel_pagamento', 'cpf_cnpj_emitente', 'razao_social', 'credor']
                        cols_existentes = [c for c in cols_fornecedor if c in df.columns]
                        
                        if cols_existentes:
                            mask_forn = pd.Series(False, index=df.index)
                            for col_f in cols_existentes:
                                for termo_f in termos_forn:
                                    mask_forn |= df[col_f].astype(str).str.lower().str.contains(termo_f, na=False)
                            df = df[mask_forn]

            # ==============================================================================
            # BLOCO DE FILTROS CONDICIONAIS DE BUSCA GERAL
            # ==============================================================================
            if filtro_geral and not df.empty:
                termo = str(filtro_geral).strip()

                if categoria_sel == "Notas de Empenho":
                    mask_num = df['numero_empenho'].astype(str).str.contains(termo, case=False, na=False)
                    mask_doc = df['numero_documento_negociante'].astype(str).str.contains(termo, case=False, na=False) if 'numero_documento_negociante' in df.columns else pd.Series(False, index=df.index)
                    mask_cred = df['nome_negociante'].astype(str).str.contains(termo, case=False, na=False) if 'nome_negociante' in df.columns else pd.Series(False, index=df.index)
                    mask_hist = df['descricao_historico_empenho'].astype(str).str.contains(termo, case=False, na=False) if 'descricao_historico_empenho' in df.columns else pd.Series(False, index=df.index)
                    mask_contrato = df['numero_contrato'].astype(str).str.contains(termo, case=False, na=False) if 'numero_contrato' in df.columns else pd.Series(False, index=df.index)

                    df.loc[mask_hist, 'match_reason'] = "Encontrado no Histórico"
                    df.loc[mask_cred, 'match_reason'] = "Credor cadastrado"
                    df.loc[mask_contrato, 'match_reason'] = "Nº Contrato"
                    df.loc[mask_doc, 'match_reason'] = "CPF/CNPJ Credor"
                    df.loc[mask_num, 'match_reason'] = "Nº Empenho"
                    mask = mask_num | mask_doc | mask_cred | mask_hist | mask_contrato

                elif categoria_sel == "Notas de Pagamento":
                    mask_num_emp = df['numero_empenho'].astype(str).str.contains(termo, case=False, na=False)
                    mask_num_pg = df['numero_nota_pagamento'].astype(str).str.contains(termo, case=False, na=False) if 'numero_nota_pagamento' in df.columns else pd.Series(False, index=df.index)
                    mask_resp = df['nome_responsavel_pagamento'].astype(str).str.contains(termo, case=False, na=False) if 'nome_responsavel_pagamento' in df.columns else pd.Series(False, index=df.index)
                    mask_doc_cx = df['numero_documento_caixa'].astype(str).str.contains(termo, case=False, na=False) if 'numero_documento_caixa' in df.columns else pd.Series(False, index=df.index)

                    df.loc[mask_doc_cx, 'match_reason'] = "Nº Doc Caixa"
                    df.loc[mask_resp, 'match_reason'] = "Responsável Pagto"
                    df.loc[mask_num_pg, 'match_reason'] = "Nº Nota Pagto"
                    df.loc[mask_num_emp, 'match_reason'] = "Nº Empenho"
                    mask = mask_num_emp | mask_num_pg | mask_resp | mask_doc_cx

                elif categoria_sel == "Liquidações":
                    mask_num_emp = df['numero_empenho'].astype(str).str.contains(termo, case=False, na=False)
                    
                    if 'numero_nota_liquidacao' in df.columns:
                        col_num_liq = 'numero_nota_liquidacao'
                    elif 'numero_nota_fiscal' in df.columns:
                        col_num_liq = 'numero_nota_fiscal'
                    elif 'numero_documento' in df.columns:
                        col_num_liq = 'numero_documento'
                    else:
                        col_num_liq = None

                    if 'descricao_historico_nota_liquidacao' in df.columns:
                        col_hist_liq = 'descricao_historico_nota_liquidacao'
                    elif 'historico' in df.columns:
                        col_hist_liq = 'historico'
                    else:
                        col_hist_liq = None

                    if col_num_liq is not None and col_num_liq in df.columns:
                        mask_num_liq = df[col_num_liq].astype(str).str.contains(termo, case=False, na=False)
                    else:
                        mask_num_liq = pd.Series(False, index=df.index)

                    if col_hist_liq is not None and col_hist_liq in df.columns:
                        mask_hist_liq = df[col_hist_liq].astype(str).str.contains(termo, case=False, na=False)
                    else:
                        mask_hist_liq = pd.Series(False, index=df.index)
                    
                    if col_hist_liq and col_hist_liq in df.columns: 
                        df.loc[mask_hist_liq, 'match_reason'] = "Histórico de Liquidação"
                    if col_num_liq and col_num_liq in df.columns: 
                        df.loc[mask_num_liq, 'match_reason'] = "Nº Liquidação"
                        
                    df.loc[mask_num_emp, 'match_reason'] = "Nº Empenho"
                    mask = mask_num_emp | mask_num_liq | mask_hist_liq

                elif categoria_sel == "Itens de Notas Fiscais":
                    col_emp_item = 'numero_nota_empenho' if 'numero_nota_empenho' in df.columns else ('numero_empenho' if 'numero_empenho' in df.columns else None)
                    
                    mask_num_emp = df[col_emp_item].astype(str).str.contains(termo, case=False, na=False) if col_emp_item else pd.Series(False, index=df.index)
                    mask_desc_item = df['descricao_item'].astype(str).str.contains(termo, case=False, na=False) if 'descricao_item' in df.columns else pd.Series(False, index=df.index)
                    mask_num_nf = df['numero_nota_fiscal'].astype(str).str.contains(termo, case=False, na=False) if 'numero_nota_fiscal' in df.columns else pd.Series(False, index=df.index)

                    df.loc[mask_num_nf, 'match_reason'] = "Nº Nota Fiscal"
                    df.loc[mask_desc_item, 'match_reason'] = "Descrição do Item"
                    if col_emp_item: df.loc[mask_num_emp, 'match_reason'] = "Nº Empenho"
                    mask = mask_num_emp | mask_desc_item | mask_num_nf

                else: # Notas Fiscais
                    mask_num_emp = df['numero_empenho'].astype(str).str.contains(termo, case=False, na=False)
                    mask_num_nf = df['numero_nota_fiscal'].astype(str).str.contains(termo, case=False, na=False) if 'numero_nota_fiscal' in df.columns else pd.Series(False, index=df.index)
                    mask_emit = df['cpf_cnpj_emitente'].astype(str).str.contains(termo, case=False, na=False) if 'cpf_cnpj_emitente' in df.columns else pd.Series(False, index=df.index)
                    mask_chave = df['numero_chave_acesso_nfe'].astype(str).str.contains(termo, case=False, na=False) if 'numero_chave_acesso_nfe' in df.columns else pd.Series(False, index=df.index)

                    df.loc[mask_chave, 'match_reason'] = "Chave de Acesso NF"
                    df.loc[mask_emit, 'match_reason'] = "CPF/CNPJ Emitente"
                    df.loc[mask_num_nf, 'match_reason'] = "Nº Nota Fiscal"
                    df.loc[mask_num_emp, 'match_reason'] = "Nº Empenho"
                    mask = mask_num_emp | mask_num_nf | mask_emit | mask_chave
                
                df = df[mask]

            st.session_state.df_resultado = df
            st.session_state.consulta_realizada = True
            
            # Formata rótulo amigável para os anos filtrados
            txt_ano = f"{data_inicial.year}" if data_inicial.year == data_final.year else f"{data_inicial.year}-{data_final.year}"
            st.session_state.filtros_aplicados = {
                "categoria_sel": categoria_sel,
                "ano_sel": txt_ano,
                "municipio_sel": municipio_sel,
                "codigo_mun_busca": codigo_mun_busca,
                "prefixo": prefixo,
                "filtro_geral": filtro_geral
            }
        else:
            st.session_state.df_resultado = pd.DataFrame()
            st.session_state.consulta_realizada = False
            txt_aviso_ano = f"no ano {data_inicial.year}" if data_inicial.year == data_final.year else f"no período {data_inicial.year}-{data_final.year}"
            st.warning(f"Nenhum arquivo encontrado para {categoria_sel} {txt_aviso_ano}. Certifique-se de realizar a extração primeiro.")

    if st.session_state.consulta_realizada:
        df = st.session_state.df_resultado
        filtros = st.session_state.filtros_aplicados
        
        st.subheader(f"LISTA DE {filtros['categoria_sel'].upper()} - {filtros['ano_sel']}")
        
        if filtros['municipio_sel'] != "Todos":
            st.write(f"📍 Município selecionado: **{opcoes_mun[filtros['municipio_sel']]['nome_municipio']}**")
            
        if not df.empty:
            st.caption(f"Foram encontrados {len(df):,} registros.")

            def highlight_term(text, term):
                if not term or not text:
                    return text
                text_str = str(text)
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                return pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text_str)

            limite = 20
            for index, row in df.head(limite).iterrows():
                match_badge_html = ""
                if 'match_reason' in row and row['match_reason']:
                    match_badge_html = f'<span class="match-badge">🔍 {row["match_reason"]}</span>'

                status_badge_html = ""
                if filtros['categoria_sel'] == "Notas de Empenho" and 'status_pagamento' in row:
                    status_class = "status-" + str(row['status_pagamento']).lower()
                    status_badge_html = f'<span class="status-badge {status_class}">{row["status_pagamento"]}</span>'

                # ==============================================================================
                # TRATAMENTO DE VARIÁVEIS POR CATEGORIA DE VISUALIZAÇÃO
                # ==============================================================================
                if filtros['categoria_sel'] == "Notas de Empenho":
                    id_doc = f"EMPENHO: {row.get('numero_empenho', 'N/A')}"
                    entidade = row.get('nome_negociante', 'Não Informado')
                    detalhe = row.get('descricao_historico_empenho', 'Sem descrição')
                    data_item = formatar_data(row.get('data_emissao_empenho'))
                    
                    val_emp = formatar_moeda(row.get('valor_empenhado', 0.0))
                    val_liq = formatar_moeda(row.get('valor_liquidado', 0.0))
                    val_pag = formatar_moeda(row.get('valor_pago', 0.0))
                    
                elif filtros['categoria_sel'] == "Notas de Pagamento":
                    id_doc = f"PAGAMENTO: {row.get('numero_nota_pagamento', 'N/A')}"
                    entidade = row.get('nome_responsavel_pagamento', 'Não Informado')
                    detalhe = f"Ref. Empenho: {row.get('numero_empenho', 'N/A')} | Doc Caixa: {row.get('numero_documento_caixa', 'N/A')}"
                    data_item = formatar_data(row.get('data_nota_pagamento'))
                    
                    val_emp = "---"
                    val_liq = "---"
                    val_pag = formatar_moeda(row.get('valor_nota_pagamento', 0.0))

                elif filtros['categoria_sel'] == "Liquidações":
                    num_liq_val = row.get('numero_nota_liquidacao', row.get('numero_nota_fiscal', row.get('numero_documento', 'N/A')))
                    id_doc = f"LIQUIDAÇÃO: {num_liq_val}"
                    entidade = f"Ref. Empenho: {row.get('numero_empenho', 'N/A')}"
                    detalhe = row.get('descricao_historico_nota_liquidacao', row.get('historico', 'Sem histórico de liquidação'))
                    
                    data_liq_col = row.get('data_nota_liquidacao', row.get('data_liquidacao', row.get('data_emissao', '')))
                    data_item = formatar_data(data_liq_col)
                    
                    val_emp = "---"
                    val_liq = formatar_moeda(row.get('valor_bruto_nota_liquidacao', row.get('valor_liquidado', row.get('valor_bruto', 0.0))))
                    val_pag = "---"

                elif filtros['categoria_sel'] == "Itens de Notas Fiscais":
                    id_doc = f"ITEM DA NF: {row.get('numero_nota_fiscal', 'N/A')}"
                    entidade = f"Item nº {row.get('numero_item', '-')}"
                    detalhe = f"Descrição: {row.get('descricao_item', 'Não informada')} | Qtd: {row.get('quantidade_item', 1)}"
                    data_item = formatar_data(row.get('data_emissao', ''))
                    
                    val_emp = "---"
                    val_liq = formatar_moeda(row.get('valor_total_item', 0.0)) 
                    val_pag = "---"
                    
                else: # Notas Fiscais
                    id_doc = f"NF: {row.get('numero_nota_fiscal', 'N/A')}"
                    entidade = f"Emitente: {row.get('cpf_cnpj_emitente', 'Não Informado')}"
                    detalhe = f"Empenho Associado: {row.get('numero_empenho', 'N/A')} | Série: {row.get('numero_serie', 'N/A')}"
                    data_item = formatar_data(row.get('data_emissao'))
                    
                    val_emp = "---"
                    val_liq = formatar_moeda(row.get('valor_bruto', 0.0))
                    val_pag = "---"

                id_doc = str(id_doc).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                entidade = str(entidade).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                detalhe = str(detalhe).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

                if filtros['filtro_geral']:
                    id_doc = highlight_term(id_doc, filtros['filtro_geral'])
                    entidade = highlight_term(entidade, filtros['filtro_geral'])
                    detalhe = highlight_term(detalhe, filtros['filtro_geral'])

                detalhe_str = str(detalhe)
                if len(detalhe_str) > 220 and not "<mark>" in detalhe_str[210:]:
                    detalhe_exibicao = detalhe_str[:220] + '...'
                else:
                    detalhe_exibicao = detalhe_str

                card_html = (
                    f'<div class="report-card">'
                    f'<div class="card-header-row">'
                    f'<div class="card-header">{id_doc} {status_badge_html}</div>'
                    f'{match_badge_html}'
                    f'</div>'
                    f'<div class="card-vendor">{entidade}</div>'
                    f'<div class="card-org">📍 {row.get("municipio_referencia", "Não Informado")}</div>'
                    f'<span class="card-date">📅 {data_item}</span>'
                    f'<div style="font-size: 0.9rem; line-height: 1.5; color: #444; margin-top: 10px; min-height: 52px;">'
                    f'{detalhe_exibicao}'
                    f'</div>'
                    f'<div class="values-grid">'
                    f'<div class="value-col"><div class="value-title">Empenhado (R$)</div><div class="value-num val-empenhado">{val_emp if val_emp == "---" else "R$ " + val_emp}</div></div>'
                    f'<div class="value-col"><div class="value-title">Liquidado (R$)</div><div class="value-num val-liquidado">{val_liq if val_liq == "---" else "R$ " + val_liq}</div></div>'
                    f'<div class="value-col"><div class="value-title">Pago (R$)</div><div class="value-num val-pago">{val_pag if val_pag == "---" else "R$ " + val_pag}</div></div>'
                    f'</div>'
                    f'</div>'
                )
                
                st.markdown(card_html, unsafe_allow_html=True)
                
                if st.button("DETALHES 🔎", key=f"btn_det_{index}", use_container_width=True):
                    if filtros['categoria_sel'] == "Notas de Pagamento":
                        exibir_modal_detalhes_pagamento(
                            row, 
                            filtros['categoria_sel'], 
                            filtros['ano_sel'], 
                            filtros['codigo_mun_busca'],
                            id_unico=index
                        )
                    else:
                        exibir_modal_detalhes(
                            row, 
                            filtros['categoria_sel'], 
                            filtros['ano_sel'], 
                            filtros['codigo_mun_busca'],
                            id_unico=index
                        )