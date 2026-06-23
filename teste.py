# consultation.py
import streamlit as st
import pandas as pd
import glob
import re
import json
import os
from pathlib import Path

# Ajuste os imports abaixo conforme a raiz real do seu projeto
from src.modules.extraction import carregar_municipios
from src.components.details_modal import exibir_modal_detalhes
from components.details_modal_pagamento import exibir_modal_detalhes_pagamento
from modules.exportadores import renderizar_botoes_exportacao
from components.details_modal import obter_caminho_arquivos_modal, carregar_e_filtrar_modal

# ==============================================================================
# CSS DOS CARDS
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
        color: #64748b; font-weight: 700; font-size: 0.8rem; 
        text-transform: uppercase; letter-spacing: 0.5px; 
    }
    .match-badge {
        background-color: #fef08a; color: #854d0e; font-size: 0.7rem;
        font-weight: bold; padding: 2px 8px; border-radius: 20px;
        border: 1px solid #fef08a; text-transform: uppercase;
    }
    .status-badge {
        font-size: 0.7rem; font-weight: bold; padding: 2px 10px;
        border-radius: 20px; text-transform: uppercase; margin-left: 8px;
    }
    .status-pago { background-color: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .status-parcial { background-color: #fef9c3; color: #a16207; border: 1px solid #fef08a; }
    .status-pendente { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }

    .card-vendor { font-size: 1.2rem; font-weight: 800; color: #0f172a; margin: 6px 0; }
    .card-org { color: #ff4b4b; font-size: 0.85rem; font-weight: 600; }
    .card-date { color: #64748b; font-size: 0.85rem; font-weight: 600; }

    .values-grid { display: flex; justify-content: space-between; gap: 12px; margin-top: 16px; }
    .value-col { flex: 1; background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center; }
    .value-title { font-size: 0.7rem; color: #64748b; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; }
    .value-num { font-family: 'Roboto Mono', monospace; font-weight: 800; font-size: 1.2rem; }
    
    .val-empenhado { color: #0f172a; }
    .val-liquidado { color: #2563eb; }
    .val-pago { color: #16a34a; }
    mark { background-color: #fef08a !important; color: #000000 !important; font-weight: bold; padding: 0 2px; border-radius: 3px; }
</style>
"""

anos = list(range(2008, 2027))

# ==============================================================================
# CARGA DO SCHEMA JSON (Direto da Raiz do Projeto)
# ==============================================================================
@st.cache_data
def carregar_configuracoes():
    """Carrega o endpoints.json da raiz do projeto espelhando a lógica de municípios"""
    try:
        # Varre os caminhos mais prováveis até a raiz do projeto
        caminhos = [
            Path(__file__).resolve().parents[2] / 'endpoints.json',
            Path(__file__).resolve().parents[1] / 'endpoints.json',
            Path(__file__).resolve().parent / 'endpoints.json',
            Path('/app/endpoints.json'),
            Path('endpoints.json')
        ]
        
        for caminho in caminhos:
            if caminho.exists():
                print(f"📂 JSON de Metadados encontrado em: {caminho}")
                with open(caminho, 'r', encoding='utf-8') as f:
                    return json.load(f)
                    
        print("🚨 ERRO: endpoints.json não encontrado em nenhum diretório base.")
        return {}
    except Exception as e:
        print(f"🚨 ERRO crítico ao carregar endpoints.json: {e}")
        return {}

config_endpoints = carregar_configuracoes()

# ==============================================================================
# FUNÇÕES DE HIGIENIZAÇÃO E CARGA
# ==============================================================================
@st.cache_data(show_spinner="Consolidando e higienizando base Parquet...")
def carregar_e_filtrar(arquivos, colunas_texto=None):
    if not arquivos: 
        return pd.DataFrame()
        
    dfs = []
    for f in arquivos:
        try:
            dfs.append(pd.read_parquet(f))
        except Exception:
            continue
            
    if not dfs: 
        return pd.DataFrame()
    
    df = pd.concat(dfs, ignore_index=True)

    if colunas_texto:
        for col in colunas_texto.keys():
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
                
    colunas_numericas = [c for c in df.columns if any(w in c.lower() for w in ['valor', 'quantidade', 'qtd'])]
    for col in colunas_numericas:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
    colunas_object = df.select_dtypes(include=['object']).columns
    for col in colunas_object:
        if colunas_texto and col in colunas_texto:
            continue 
        df[col] = df[col].fillna("").astype(str).str.strip()
        
    return df

def formatar_moeda(valor):
    try:
        if pd.isna(valor) or valor is None: 
            return "0,00"
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError): 
        return "0,00"

def formatar_data(data_raw):
    try:
        if pd.isna(data_raw) or data_raw is None or str(data_raw).strip() == "":
            return "Não Informada"
            
        data_str = str(data_raw).split('T')[0].strip()
        if '-' in data_str:
            partes = data_str.split('-')
            if len(partes) == 3:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        elif len(data_str) == 8 and data_str.isdigit():
            return f"{data_str[6:8]}/{data_str[4:6]}/{data_str[0:4]}"
            
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
# MOTOR GENÉRICO DE FILTRAGEM (O "Cérebro" Data-Driven)
# ==============================================================================
def filtrar_dataframe(df, filtros_din, busca_geral, filtro_forn, config_atual):
    if df.empty: 
        return df

    # 1. Filtros Dinâmicos da UI (Série NF, Quantidade, Status, etc)
    for campo, valor in filtros_din.items():
        if campo in df.columns and valor and valor != "TODOS":
            if isinstance(valor, (int, float)) and valor > 0:
                df = df[df[campo] >= valor]
            elif isinstance(valor, str):
                df = df[df[campo].astype(str).str.upper().str.contains(valor.upper(), na=False)]

    # 2. Busca Geral Dinâmica (Varre as colunas mapeadas no JSON)
    if busca_geral:
        termo = str(busca_geral).strip()
        mask_global = pd.Series(False, index=df.index)
        regras = config_atual.get("colunas_texto", {})
        
        for col, motivo in regras.items():
            if col in df.columns:
                mask_col = df[col].astype(str).str.contains(termo, case=False, na=False)
                df.loc[mask_col, 'match_reason'] = motivo
                mask_global |= mask_col
                
        if regras: 
            df = df[mask_global]

    # 3. Filtro de Fornecedor / Responsável
    if filtro_forn:
        termos_f = [t.strip() for t in filtro_forn.split(",") if t.strip()]
        col_fornecedores = ['nome_negociante', 'numero_documento_negociante', 'nome_responsavel_pagamento', 'cpf_cnpj_emitente', 'nome_emitente', 'razao_social', 'orgao']
        col_existentes = [c for c in col_fornecedores if c in df.columns]
        
        if col_existentes:
            mask_f_global = pd.Series(False, index=df.index)
            for t in termos_f:
                mask_t = pd.Series(False, index=df.index)
                for c in col_existentes:
                    mask_t |= df[c].astype(str).str.contains(t, case=False, na=False)
                mask_f_global |= mask_t
            df = df[mask_f_global]

    return df

# ==============================================================================
# ADAPTADOR VISUAL DE CARDS (Tradutor universal para as 11 tabelas)
# ==============================================================================
def extrair_dados_card(row, categoria):
    """Analisa a linha e devolve os textos e valores exatos para o HTML não quebrar"""
    id_doc = f"REGISTRO: {row.get('numero_documento', row.get('id', 'N/A'))}"
    entidade = row.get('nome_negociante', row.get('nome_responsavel_pagamento', row.get('razao_social', row.get('orgao', 'Não Informado'))))
    detalhe = row.get('descricao_historico_empenho', row.get('descricao_item', row.get('descricao_bem', row.get('historico', 'Sem descrição detalhada'))))
    
    col_dt = next((c for c in row.keys() if 'data' in c.lower()), None)
    data_item = formatar_data(row.get(col_dt)) if col_dt else "Não informada"

    t_emp, t_liq, t_pag = "Empenhado (R$)", "Liquidado (R$)", "Pago (R$)"
    v_emp, v_liq, v_pag = "---", "---", "---"

    if categoria == "Notas de Empenho":
        id_doc = f"EMPENHO: {row.get('numero_empenho', 'N/A')}"
        v_emp = formatar_moeda(row.get('valor_empenhado'))
        v_liq = formatar_moeda(row.get('valor_liquidado'))
        v_pag = formatar_moeda(row.get('valor_pago'))

    elif categoria == "Notas de Pagamento":
        id_doc = f"PAGAMENTO: {row.get('numero_nota_pagamento', 'N/A')}"
        entidade = row.get('nome_responsavel_pagamento', 'Não Informado')
        detalhe = f"Ref. Empenho: {row.get('numero_empenho','N/A')} | Doc Caixa: {row.get('numero_documento_caixa','N/A')}"
        v_pag = formatar_moeda(row.get('valor_nota_pagamento'))

    elif categoria == "Liquidações":
        num_liq_val = row.get('numero_nota_liquidacao', row.get('numero_nota_fiscal', row.get('numero_documento', 'N/A')))
        id_doc = f"LIQUIDAÇÃO: {num_liq_val}"
        entidade = f"Ref. Empenho: {row.get('numero_empenho', 'N/A')}"
        detalhe = row.get('descricao_historico_nota_liquidacao', row.get('historico', 'Sem histórico de liquidação'))
        v_liq = formatar_moeda(row.get('valor_bruto_nota_liquidacao', row.get('valor_liquidado', row.get('valor_bruto'))))

    elif categoria == "Itens de Notas Fiscais":
        id_doc = f"ITEM DA NF: {row.get('numero_nota_fiscal', 'N/A')}"
        entidade = f"Item nº {row.get('numero_item', '-')}"
        detalhe = f"Descrição: {row.get('descricao_item', 'Não informada')} | Qtd: {row.get('quantidade_item', 1)}"
        t_liq, v_liq = "Valor Total Item", formatar_moeda(row.get('valor_total_item'))

    elif categoria == "Notas Fiscais":
        id_doc = f"NF: {row.get('numero_nota_fiscal', 'N/A')}"
        entidade = f"Emitente: {row.get('cpf_cnpj_emitente', 'Não Informado')}"
        detalhe = f"Empenho Associado: {row.get('numero_empenho', 'N/A')} | Série: {row.get('numero_serie', row.get('serie_nota_fiscal', 'N/A'))}"
        t_liq, v_liq = "Valor da NF", formatar_moeda(row.get('valor_nota_fiscal', row.get('valor_bruto')))

    else: # Tabelas de Bens Incorporados e Gestão Patrimonial
        id_doc = f"PATRIMÔNIO: {row.get('numero_tombamento', row.get('numero_patrimonio', 'N/A'))}"
        entidade = row.get('especificacao_bem', 'Registro Patrimonial')
        detalhe = row.get('descricao_bem', row.get('descricao', 'Sem descrição do bem'))
        t_emp, v_emp = "Valor do Bem", formatar_moeda(row.get('valor_bem', row.get('valor_atual', row.get('valor_incorporacao', row.get('valor_bruto', 0.0)))))

    return id_doc, entidade, detalhe, data_item, t_emp, t_liq, t_pag, v_emp, v_liq, v_pag

# ==============================================================================
# APLICAÇÃO PRINCIPAL (Interface + Orquestrador)
# ==============================================================================
def render_consultation_page():
    st.header("🔍 Consulta Detalhada")
    st.markdown(CSS_CARDS, unsafe_allow_html=True)

    # Inicialização do Estado
    for k in ["consulta_realizada", "df_resultado", "filtros_aplicados"]:
        if k not in st.session_state: 
            st.session_state[k] = False if k == "consulta_realizada" else (pd.DataFrame() if k == "df_resultado" else {})

    lista_municipios = carregar_municipios()
    opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}
    categorias_disponiveis = list(config_endpoints.keys())

    if not categorias_disponiveis:
        st.warning("⚠️ O arquivo endpoints.json não foi carregado corretamente. Verifique a raiz do projeto.")
        return

    with st.expander("Opções de Filtro", expanded=not st.session_state.consulta_realizada):
        categoria_sel = st.selectbox("Tipo de Documento", categorias_disponiveis)
        config_atual = config_endpoints.get(categoria_sel, {})
        
        # FILTROS BASE
        col_ini, col_fim, col_mun = st.columns(3)
        ano_inicial = col_ini.selectbox("Ano Inicial", anos, index=2)
        ano_final = col_fim.selectbox("Ano Final", anos, index=5)
        municipio_sel = col_mun.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(f"🎯 Filtros específicos para: **{categoria_sel}**")
        
        # RENDERIZAÇÃO DINÂMICA DO SCHEMA (Sem campos numéricos de valor)
        filtros_dinamicos = {}
        campos_schema = config_atual.get("campos_ui", [])

        if campos_schema:
            cols = st.columns(len(campos_schema))
            for i, c in enumerate(campos_schema):
                with cols[i]:
                    if c["tipo"] == "select":
                        filtros_dinamicos[c["id"]] = st.selectbox(c["label"], c["opcoes"])
                    elif c["tipo"] == "number":
                        filtros_dinamicos[c["id"]] = st.number_input(c["label"], value=int(c.get("default", 0)), step=int(c.get("step", 1)))
                    elif c["tipo"] == "text":
                        filtros_dinamicos[c["id"]] = st.text_input(c["label"], placeholder=c.get("placeholder", ""))
        else:
            st.write("*(Nenhum filtro avançado configurado para este documento)*")

        st.divider()
        
        if ano_inicial > ano_final:
            st.error("⚠️ O Ano Inicial não pode ser maior que o Ano Final.")
            btn_consultar = False
        else:
            col_b, col_f, col_btn = st.columns([5, 3, 2])
            filtro_geral = col_b.text_input("Busca Geral", placeholder="Nº empenho, histórico, contrato, patrimônio...").strip()
            filtro_fornecedor = col_f.text_input("Fornecedor / Responsável", placeholder="CNPJ, Razão Social...").strip()
            
            col_btn.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
            btn_consultar = col_btn.button("Consultar", use_container_width=True)

    # ==============================================================================
    # DISPARO DA CONSULTA (O Controller Orquestrador)
    # ==============================================================================
    if btn_consultar and ano_inicial <= ano_final:
        with st.spinner(f"Processando bases de {categoria_sel}..."):
            prefixo = config_atual.get("prefixo")
            codigo_mun_busca = "Todos" if municipio_sel == "Todos" else opcoes_mun[municipio_sel]['codigo_municipio']

            dfs_anos = []
            liq_map, pag_map = {}, {}
            
            def get_col(df, nomes): 
                return next((c for c in nomes if c in df.columns), None)

            # Lógica Exclusiva de Acúmulo para Empenhos (Mantida intacta)
            if categoria_sel == "Notas de Empenho":
                df_liq_g, df_pg_g = pd.DataFrame(), pd.DataFrame()
                for a in range(int(ano_inicial), int(ano_final) + 1):
                    df_liq_g = pd.concat([df_liq_g, carregar_e_filtrar(obter_caminho_arquivos("liquidacoes", a, codigo_mun_busca))], ignore_index=True)
                    df_pg_g = pd.concat([df_pg_g, carregar_e_filtrar(obter_caminho_arquivos("notas_pagamentos", a, codigo_mun_busca))], ignore_index=True)
                
                if not df_liq_g.empty:
                    df_liq_g['ch'] = df_liq_g['codigo_municipio'].astype(str) + "_" + df_liq_g.get('exercicio_orcamento', '').astype(str) + "_" + df_liq_g['codigo_orgao'].astype(str) + "_" + df_liq_g['numero_empenho'].astype(str)
                    c_liq = get_col(df_liq_g, ['valor_bruto_nota_liquidacao', 'valor_liquidado', 'valor_bruto'])
                    if c_liq: 
                        liq_map = df_liq_g.groupby('ch')[c_liq].apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()).to_dict()

                if not df_pg_g.empty:
                    df_pg_g['ch'] = df_pg_g['codigo_municipio'].astype(str) + "_" + df_pg_g.get('exercicio_orcamento', '').astype(str) + "_" + df_pg_g['codigo_orgao'].astype(str) + "_" + df_pg_g['numero_empenho'].astype(str)
                    pag_map = df_pg_g.groupby('ch')['valor_nota_pagamento'].apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()).to_dict()

            # Loop de Carga por Ano
            for a in range(int(ano_inicial), int(ano_final) + 1):
                arquivos = obter_caminho_arquivos(prefixo, a, codigo_mun_busca)
                if not arquivos: 
                    continue
                    
                df_ano = carregar_e_filtrar(arquivos, colunas_texto=config_atual.get("colunas_texto", {}))
                if df_ano.empty: 
                    continue

                if municipio_sel != "Todos" and 'municipio_referencia' in df_ano.columns:
                    df_ano = df_ano[df_ano['municipio_referencia'].str.upper() == opcoes_mun[municipio_sel]['nome_municipio'].upper()]
                if df_ano.empty: 
                    continue

                df_ano['match_reason'] = ""

                # Regra de Negócio Preditiva de Pagamento para Empenhos
                if categoria_sel == "Notas de Empenho":
                    df_ano['ch'] = df_ano['codigo_municipio'].astype(str) + "_" + df_ano.get('exercicio_orcamento', str(a)).astype(str) + "_" + df_ano['codigo_orgao'].astype(str) + "_" + df_ano['numero_empenho'].astype(str)
                    df_ano['valor_liquidado'] = df_ano['ch'].map(liq_map).fillna(0.0)
                    df_ano['valor_pago'] = df_ano['ch'].map(pag_map).fillna(0.0)
                    df_ano['status_pagamento'] = df_ano.apply(lambda r: "PENDENTE" if float(r.get('valor_pago',0)) <= 0 else ("PAGO" if float(r.get('valor_pago',0)) >= float(r.get('valor_empenhado',0)) else "PARCIAL"), axis=1)

                dfs_anos.append(df_ano)

            df_consolidado = pd.concat(dfs_anos, ignore_index=True) if dfs_anos else pd.DataFrame()

            # Executa a filtragem passando pelo nosso Motor Genérico
            df_final = filtrar_dataframe(df_consolidado, filtros_dinamicos, filtro_geral, filtro_fornecedor, config_atual)

            # Salva o resultado no estado da sessão
            st.session_state.df_resultado = df_final
            st.session_state.consulta_realizada = True
            st.session_state.filtros_aplicados = {
                "categoria_sel": categoria_sel, "ano_inicial": ano_inicial, "ano_final": ano_final,
                "municipio_sel": municipio_sel, "codigo_mun_busca": codigo_mun_busca, "prefixo": prefixo,
                "filtro_geral": filtro_geral, "filtro_fornecedor": filtro_fornecedor, **filtros_dinamicos
            }

    # ==============================================================================
    # RENDERIZAÇÃO DOS RESULTADOS (Cards Visuais)
    # ==============================================================================
    if st.session_state.consulta_realizada:
        df = st.session_state.df_resultado
        filtros = st.session_state.filtros_aplicados
        
        st.subheader(f"LISTA DE {filtros['categoria_sel'].upper()} - {filtros['ano_inicial']} A {filtros['ano_final']}")
        if filtros['municipio_sel'] != "Todos": 
            st.write(f"📍 Município: **{opcoes_mun[filtros['municipio_sel']]['nome_municipio']}**")
            
        if not df.empty:
            st.caption(f"Foram encontrados **{len(df):,}** registros.")

            def highlight_term(text, term):
                if not term or not text: 
                    return text
                return re.compile(re.escape(term), re.IGNORECASE).sub(lambda m: f"<mark>{m.group(0)}</mark>", str(text))

            limite = 20
            for index, row in df.head(limite).iterrows():
                
                # Tradutor Universal de colunas para o Card
                id_doc, entidade, detalhe, data_item, t_emp, t_liq, t_pag, v_emp, v_liq, v_pag = extrair_dados_card(row, filtros['categoria_sel'])

                match_html = f'<span class="match-badge">🔍 {row["match_reason"]}</span>' if row.get('match_reason') else ""
                status_html = f'<span class="status-badge status-{str(row["status_pagamento"]).lower()}">{row["status_pagamento"]}</span>' if filtros['categoria_sel'] == "Notas de Empenho" and row.get('status_pagamento') else ""

                if filtros['filtro_geral']:
                    id_doc = highlight_term(id_doc, filtros['filtro_geral'])
                    entidade = highlight_term(entidade, filtros['filtro_geral'])
                    detalhe = highlight_term(detalhe, filtros['filtro_geral'])

                detalhe_exibicao = str(detalhe)[:220] + '...' if len(str(detalhe)) > 220 and "<mark>" not in str(detalhe)[210:] else str(detalhe)

                # Montagem Inteligente do Grid de Valores (Oculta colunas sem dados)
                grid_valores_html = ""
                if v_emp != "---": 
                    grid_valores_html += f'<div class="value-col"><div class="value-title">{t_emp}</div><div class="value-num val-empenhado">R$ {v_emp}</div></div>'
                if v_liq != "---": 
                    grid_valores_html += f'<div class="value-col"><div class="value-title">{t_liq}</div><div class="value-num val-liquidado">R$ {v_liq}</div></div>'
                if v_pag != "---": 
                    grid_valores_html += f'<div class="value-col"><div class="value-title">{t_pag}</div><div class="value-num val-pago">R$ {v_pag}</div></div>'

                card_html = (
                    f'<div class="report-card">'
                    f'<div class="card-header-row"><div class="card-header">{id_doc} {status_html}</div>{match_html}</div>'
                    f'<div class="card-vendor">{entidade}</div>'
                    f'<div class="card-org">📍 {row.get("municipio_referencia", "Município não mapeado")}</div>'
                    f'<span class="card-date">📅 {data_item}</span>'
                    f'<div style="font-size: 0.9rem; line-height: 1.5; color: #444; margin-top: 10px; min-height: 52px;">{detalhe_exibicao}</div>'
                    f'<div class="values-grid">{grid_valores_html}</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
                
                if st.button("DETALHES 🔎", key=f"btn_det_{index}", use_container_width=True):
                    if filtros['categoria_sel'] == "Notas de Pagamento":
                        exibir_modal_detalhes_pagamento(row, filtros['categoria_sel'], filtros['ano_inicial'], filtros['codigo_mun_busca'], id_unico=index)
                    else:
                        exibir_modal_detalhes(row, filtros['categoria_sel'], filtros['ano_inicial'], filtros['codigo_mun_busca'], id_unico=index)

            if len(df) > limite: 
                st.info(f"Exibindo os {limite} primeiros registros de alta relevância.")

            st.divider()
            st.markdown("### 📥 Opções de Exportação")
            
            csv_data = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label=f"📥 Exportar Grid Atual ({len(df):,} linhas)", 
                data=csv_data, 
                file_name=f"TCE_{filtros['prefixo']}_{filtros['ano_inicial']}_{filtros['ano_final']}.csv", 
                mime="text/csv", use_container_width=True
            )
            
            renderizar_botoes_exportacao(
                df_empenhos_filtrados=df, ano_inicial=filtros['ano_inicial'], ano_final=filtros['ano_final'], 
                codigo_mun=filtros['codigo_mun_busca'], obter_caminho_func=obter_caminho_arquivos_modal, 
                carregar_e_filtrar_func=carregar_e_filtrar_modal 
            )
        else:
            st.warning("Nenhum registro encontrado para os filtros aplicados.")
    else:
        st.info("Selecione os parâmetros acima e clique em 'Consultar' para carregar a base de dados.")