# consultation.py
import streamlit as st
import pandas as pd
import glob
import re
from main import carregar_municipios
# IMPORTANDO O MODAL ISOLADO
from details_modal import exibir_modal_detalhes

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
        return sorted(glob.glob(f"data/{prefixo}_{ano}_*.parquet"))
    return sorted(glob.glob(f"data/{prefixo}_{ano}_*_{codigo_mun}.parquet"))


# ==============================================================================
# RENDERIZADOR DA PÁGINA
# ==============================================================================
def render_consultation_page():
    st.header("🔍 Consulta Detalhada")
    st.markdown(CSS_CARDS, unsafe_allow_html=True)

    # Inicializa variáveis de estado se não existirem
    if "consulta_realizada" not in st.session_state:
        st.session_state.consulta_realizada = False
    if "df_resultado" not in st.session_state:
        st.session_state.df_resultado = pd.DataFrame()
    if "filtros_aplicados" not in st.session_state:
        st.session_state.filtros_aplicados = {}

    lista_municipios = carregar_municipios()
    opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}

    with st.expander("Opções de Filtro", expanded=not st.session_state.consulta_realizada):
        categoria_sel = st.selectbox("Tipo de Documento", ["Notas de Empenho", "Notas Fiscais", "Notas de Pagamento"])
        
        if categoria_sel == "Notas de Empenho":
            col_ano, col_mun, col_pag = st.columns(3)
            ano_sel = col_ano.selectbox("Ano", [2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026], index=5)
            municipio_sel = col_mun.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
            pagamento_sel = col_pag.selectbox("Filtro de Pagamento", ["TODOS", "PENDENTE", "PARCIAL", "PAGO"])
        else:
            col_ano, col_mun = st.columns(2)
            ano_sel = col_ano.selectbox("Ano", [2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026], index=5)
            municipio_sel = col_mun.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
            pagamento_sel = "TODOS"
        
        col_busca, col_botao = st.columns([8, 2])
        filtro_geral = col_busca.text_input(
            "Busca Geral", 
            placeholder="Digite nº empenho, credor, CNPJ, responsável ou conteúdo do histórico...",
            label_visibility="visible"
        ).strip()
        
        col_botao.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
        btn_consultar = col_botao.button("Consultar", use_container_width=True)

    # Processa a busca se o botão for clicado
    if btn_consultar:
        mapa_prefixos = {
            "Notas de Empenho": "notas_empenho",
            "Notas Fiscais": "notas_fiscais",
            "Notas de Pagamento": "notas_pagamentos"
        }

        prefixo = mapa_prefixos[categoria_sel]
        codigo_mun_busca = "Todos"
        if municipio_sel != "Todos":
            codigo_mun_busca = opcoes_mun[municipio_sel]['codigo_municipio']

        arquivos = obter_caminho_arquivos(prefixo, ano_sel, codigo_mun_busca)

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
                    
                    arq_nf = obter_caminho_arquivos("notas_fiscais", ano_sel, codigo_mun_busca)
                    df_nf = carregar_e_filtrar(arq_nf)
                    liq_map = {}
                    
                    if not df_nf.empty:
                        df_nf['codigo_municipio'] = df_nf['codigo_municipio'].astype(str)
                        df_nf['codigo_orgao'] = df_nf['codigo_orgao'].astype(str)
                        df_nf['numero_empenho'] = df_nf['numero_empenho'].astype(str)
                        df_nf['chave_composta'] = df_nf['codigo_municipio'].str.strip() + "_" + df_nf['codigo_orgao'].str.strip() + "_" + df_nf['numero_empenho'].str.strip()
                        liq_map = df_nf.groupby('chave_composta')['valor_bruto'].sum().to_dict()
                        
                    arq_pg = obter_caminho_arquivos("notas_pagamentos", ano_sel, codigo_mun_busca)
                    df_pg = carregar_e_filtrar(arq_pg)
                    pag_map = {}
                    
                    if not df_pg.empty:
                        df_pg['codigo_municipio'] = df_pg['codigo_municipio'].astype(str)
                        df_pg['codigo_orgao'] = df_pg['codigo_orgao'].astype(str)
                        df_pg['numero_empenho'] = df_pg['numero_empenho'].astype(str)
                        df_pg['chave_composta'] = df_pg['codigo_municipio'].str.strip() + "_" + df_pg['codigo_orgao'].str.strip() + "_" + df_pg['numero_empenho'].str.strip()
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

            if filtro_geral and not df.empty:
                if categoria_sel == "Notas de Empenho":
                    mask_num = df['numero_empenho'].astype(str).str.contains(filtro_geral, case=False, na=False)
                    mask_doc = df['numero_documento_negociante'].astype(str).str.contains(filtro_geral, case=False, na=False)
                    mask_cred = df['nome_negociante'].str.contains(filtro_geral, case=False, na=False)
                    mask_hist = df['descricao_historico_empenho'].str.contains(filtro_geral, case=False, na=False)
                    mask_contrato = df['numero_contrato'].astype(str).str.contains(filtro_geral, case=False, na=False)

                    df.loc[mask_hist, 'match_reason'] = "Encontrado no Histórico"
                    df.loc[mask_cred, 'match_reason'] = "Credor cadastrado"
                    df.loc[mask_contrato, 'match_reason'] = "Nº Contrato"
                    df.loc[mask_doc, 'match_reason'] = "CPF/CNPJ Credor"
                    df.loc[mask_num, 'match_reason'] = "Nº Empenho"
                    mask = mask_num | mask_doc | mask_cred | mask_hist | mask_contrato

                elif categoria_sel == "Notas de Pagamento":
                    mask_num_emp = df['numero_empenho'].astype(str).str.contains(filtro_geral, case=False, na=False)
                    mask_num_pg = df['numero_nota_pagamento'].astype(str).str.contains(filtro_geral, case=False, na=False)
                    mask_resp = df['nome_responsavel_pagamento'].str.contains(filtro_geral, case=False, na=False)
                    mask_doc_cx = df['numero_documento_caixa'].astype(str).str.contains(filtro_geral, case=False, na=False)

                    df.loc[mask_doc_cx, 'match_reason'] = "Nº Doc Caixa"
                    df.loc[mask_resp, 'match_reason'] = "Responsável Pagto"
                    df.loc[mask_num_pg, 'match_reason'] = "Nº Nota Pagto"
                    df.loc[mask_num_emp, 'match_reason'] = "Nº Empenho"
                    mask = mask_num_emp | mask_num_pg | mask_resp | mask_doc_cx

                else:
                    mask_num_emp = df['numero_empenho'].astype(str).str.contains(filtro_geral, case=False, na=False)
                    mask_num_nf = df['numero_nota_fiscal'].astype(str).str.contains(filtro_geral, case=False, na=False)
                    mask_emit = df['cpf_cnpj_emitente'].astype(str).str.contains(filtro_geral, case=False, na=False)
                    mask_chave = df['numero_chave_acesso_nfe'].astype(str).str.contains(filtro_geral, case=False, na=False)

                    df.loc[mask_chave, 'match_reason'] = "Chave de Acesso NF"
                    df.loc[mask_emit, 'match_reason'] = "CPF/CNPJ Emitente"
                    df.loc[mask_num_nf, 'match_reason'] = "Nº Nota Fiscal"
                    df.loc[mask_num_emp, 'match_reason'] = "Nº Empenho"
                    mask = mask_num_emp | mask_num_nf | mask_emit | mask_chave
                
                df = df[mask]

            # Salva o resultado e os parâmetros nos estados de sessão
            st.session_state.df_resultado = df
            st.session_state.consulta_realizada = True
            st.session_state.filtros_aplicados = {
                "categoria_sel": categoria_sel,
                "ano_sel": ano_sel,
                "municipio_sel": municipio_sel,
                "codigo_mun_busca": codigo_mun_busca,
                "prefixo": prefixo,
                "filtro_geral": filtro_geral
            }
        else:
            st.session_state.df_resultado = pd.DataFrame()
            st.session_state.consulta_realizada = False
            st.warning(f"Nenhum arquivo encontrado para {categoria_sel} em {ano_sel}. Certifique-se de realizar a extração primeiro.")

    # Renderiza os resultados
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

            limite = 15
            for index, row in df.head(limite).iterrows():
                match_badge_html = ""
                if 'match_reason' in row and row['match_reason']:
                    match_badge_html = f'<span class="match-badge">🔍 {row["match_reason"]}</span>'

                status_badge_html = ""
                if filtros['categoria_sel'] == "Notas de Empenho" and 'status_pagamento' in row:
                    status_class = "status-" + str(row['status_pagamento']).lower()
                    status_badge_html = f'<span class="status-badge {status_class}">{row["status_pagamento"]}</span>'

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
                    
                else: 
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
                    f'<div class="value-col"><div class="value-title">Empenhado (R$)</div><div class="value-num val-empenhado">R$ {val_emp}</div></div>'
                    f'<div class="value-col"><div class="value-title">Liquidado (R$)</div><div class="value-num val-liquidado">R$ {val_liq}</div></div>'
                    f'<div class="value-col"><div class="value-title">Pago (R$)</div><div class="value-num val-pago">R$ {val_pag}</div></div>'
                    f'</div>'
                    f'</div>'
                )
                
                st.markdown(card_html, unsafe_allow_html=True)
                
                # Chamando o botão que consome a função importada de details_modal.py
                if st.button(f"🔎 DETALHES DO EMPENHO: {row.get('numero_empenho', index)}", key=f"det_{index}", use_container_width=True):
                    exibir_modal_detalhes(row, filtros['categoria_sel'], filtros['ano_sel'], filtros['codigo_mun_busca'])

            if len(df) > limite:
                st.info(f"Exibindo os {limite} primeiros resultados para garantir excelente tempo de carregamento da interface.")

            st.divider()
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(f"📥 Exportar Base Completa ({len(df):,} linhas)", csv, f"TCE_{filtros['prefixo']}_{filtros['ano_sel']}.csv", "text/csv", use_container_width=True)
        else:
            st.warning("Nenhum registro encontrado para os filtros aplicados.")
    else:
        st.info("Selecione os parâmetros e clique em 'Consultar' para visualizar os resultados.")