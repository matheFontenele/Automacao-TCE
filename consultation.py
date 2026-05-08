import streamlit as st
import pandas as pd
import glob
import os
import re
from main import carregar_municipios

# Definição de Estilo dos Cards (CSS) com suporte a badges e marcações de busca
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

    .card-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }

    .card-header { 
        color: #666; 
        font-weight: 700; 
        font-size: 0.75rem; 
        text-transform: uppercase; 
        letter-spacing: 1px; 
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

    .card-vendor { font-size: 1.15rem; font-weight: 800; color: #1E1E24; margin: 5px 0; }
    .card-org { font-size: 0.85rem; color: #ff4b4b; font-weight: 600; margin-bottom: 12px; }
    .card-value { font-family: 'Roboto Mono', monospace; font-weight: 800; color: #15803d; font-size: 1.6rem; }

    mark {
        background-color: #fef08a !important;
        color: #000000 !important;
        font-weight: bold;
        padding: 0 2px;
        border-radius: 3px;
    }

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

# Função auxiliar para formatar moeda de forma segura e no padrão PT-BR
def formatar_moeda(valor):
    try:
        if pd.isna(valor) or valor is None:
            return "0,00"
        val_float = float(valor)
        return f"{val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

def render_consultation_page():
    st.header("🔍 Consulta Detalhada")
    st.markdown(CSS_CARDS, unsafe_allow_html=True)

    # Carrega a lista de municípios usando a função do main.py
    lista_municipios = carregar_municipios()
    opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m['nome_municipio'] for m in lista_municipios}

    # 1. Área de Filtros
    with st.expander("Opções de Filtro", expanded=True):
        col_ano, col_tipo, col_mun = st.columns(3)
        ano_sel = col_ano.selectbox("Ano", [2020, 2021, 2022, 2023, 2024, 2025, 2026], index=6)
        categoria_sel = col_tipo.selectbox("Tipo de Documento", ["Notas de Empenho", "Notas Fiscais", "Notas de Pagamento"])
        municipio_sel = col_mun.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
        
        col_busca, col_botao = st.columns([8, 2])
        filtro_geral = col_busca.text_input(
            "Busca Geral", 
            placeholder="Digite nº empenho, credor, CNPJ, responsável ou conteúdo do histórico...",
            label_visibility="visible"
        ).strip()
        
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

        if municipio_sel == "Todos":
            padrao_busca = f"data/{prefixo}_{ano_sel}_*.parquet"
        else:
            match = re.search(r'\((\d+)\)', municipio_sel)
            codigo_mun = match.group(1) if match else "*"
            padrao_busca = f"data/{prefixo}_{ano_sel}_*_{codigo_mun}.parquet"

        arquivos = sorted(glob.glob(padrao_busca))

        if arquivos:
            df = carregar_e_filtrar(arquivos)

            if municipio_sel != "Todos" and not df.empty and 'municipio_referencia' in df.columns:
                nome_municipio_real = opcoes_mun[municipio_sel]
                df = df[df['municipio_referencia'].str.upper() == nome_municipio_real.upper()]

            if not df.empty:
                df['match_reason'] = ""

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

                else: # Notas Fiscais
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

            st.subheader(f"LISTA DE {categoria_sel.upper()} - {ano_sel}")
            
            if municipio_sel != "Todos":
                st.write(f"📍 Município selecionado: **{opcoes_mun[municipio_sel]}**")
                
            st.caption(f"Foram encontrados {len(df):,} registros.")

            def highlight_term(text, term):
                if not term or not text:
                    return text
                text_str = str(text)
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                return pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text_str)

            limite = 50
            for _, row in df.head(limite).iterrows():
                match_badge_html = ""
                if 'match_reason' in row and row['match_reason']:
                    match_badge_html = f'<span class="match-badge">🔍 {row["match_reason"]}</span>'

                if categoria_sel == "Notas de Empenho":
                    id_doc = f"EMPENHO: {row['numero_empenho']}"
                    entidade = row['nome_negociante']
                    detalhe = row['descricao_historico_empenho']
                    valor_bruto = row['valor_empenhado']
                    label = "Empenhado (R$)"
                    
                elif categoria_sel == "Notas de Pagamento":
                    id_doc = f"PAGAMENTO: {row['numero_nota_pagamento']}"
                    entidade = row['nome_responsavel_pagamento']
                    detalhe = f"Ref. Empenho: {row['numero_empenho']} | Doc Caixa: {row['numero_documento_caixa']}"
                    valor_bruto = row['valor_nota_pagamento']
                    label = "Pago (R$)"
                    
                else: 
                    id_doc = f"NF: {row['numero_nota_fiscal']}"
                    entidade = f"Emitente: {row['cpf_cnpj_emitente']}"
                    detalhe = f"Empenho Associado: {row['numero_empenho']} | Série: {row['numero_serie']}"
                    valor_bruto = row['valor_bruto']
                    label = "Bruto (R$)"

                valor_formatado = formatar_moeda(valor_bruto)

                id_doc = str(id_doc).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                entidade = str(entidade).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                detalhe = str(detalhe).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

                if filtro_geral:
                    id_doc = highlight_term(id_doc, filtro_geral)
                    entidade = highlight_term(entidade, filtro_geral)
                    detalhe = highlight_term(detalhe, filtro_geral)

                detalhe_str = str(detalhe)
                if len(detalhe_str) > 250 and not "<mark>" in detalhe_str[240:]:
                    detalhe_exibicao = detalhe_str[:250] + '...'
                else:
                    detalhe_exibicao = detalhe_str

                # Construção do card HTML com suporte a badges e marcações de busca
                card_html = (
                    f'<div class="report-card">'
                    f'<div style="display: flex; justify-content: space-between; align-items: stretch;">'
                    f'<div style="flex: 3; border-right: 1px solid rgba(0,0,0,0.05); padding-right: 25px;">'
                    f'<div class="card-header-row">'
                    f'<div class="card-header">{id_doc}</div>'
                    f'{match_badge_html}'
                    f'</div>'
                    f'<div class="card-vendor">{entidade}</div>'
                    f'<div class="card-org">📍 {row["municipio_referencia"]}</div>'
                    f'<div style="font-size: 0.9rem; line-height: 1.5; color: #444; margin-top: 10px;">'
                    f'{detalhe_exibicao}'
                    f'</div>'
                    f'</div>'
                    f'<div style="flex: 1.2; text-align: right; padding-left: 25px; display: flex; flex-direction: column; justify-content: center; background-color: rgba(0,0,0,0.01);">'
                    f'<div style="font-size: 0.7rem; color: #888; font-weight: bold;">{label}</div>'
                    f'<div class="card-value">R$ {valor_formatado}</div>'
                    f'<div style="margin-top: 15px;"><a href="#" class="btn-fake">🔍 DETALHES</a></div>'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                )
                
                st.markdown(card_html, unsafe_allow_html=True)

            if len(df) > limite:
                st.info(f"Mostrando os {limite} primeiros registros para garantir a performance.")

            st.divider()
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(f"📥 Exportar Base Completa ({len(df):,} linhas)", csv, f"TCE_{prefixo}_{ano_sel}.csv", "text/csv", use_container_width=True)
        else:
            st.warning(f"Nenhum arquivo encontrado para {categoria_sel} em {ano_sel}. Certifique-se de realizar a extração primeiro.")
    else:
        st.info("Ajuste os filtros acima e clique em '🚀 Consultar' para visualizar os dados.")