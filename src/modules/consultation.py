# consultation.py
import streamlit as st
import pandas as pd
import glob
import re
import json
import os
from pathlib import Path
from src.modules.extraction import carregar_municipios
from src.components.details_modal import exibir_modal_detalhes
from components.details_modal_pagamento import exibir_modal_detalhes_pagamento
from modules.exportadores import renderizar_botoes_exportacao
from components.details_modal import obter_caminho_arquivos_modal, carregar_e_filtrar_modal
from components.dynamic_card import renderizar_card_dinamico

anos = list(range(2008, 2027))

# ==============================================================================
# FUNÇÕES DE TRATAMENTO E CARREGAMENTO DE DADOS (Consulta Geral)
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

# FUNÇÕES DE HIGIENIZAÇÃO E CARGA
@st.cache_data(show_spinner="Consolidando e higienizando base Parquet...")
def carregar_e_filtrar(arquivos, colunas_texto=None):
    """Carrega os arquivos Parquet de forma geral e executa a limpeza das colunas correspondentes"""
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
    
    # Consolida os dados em um único DataFrame
    df = pd.concat(dfs, ignore_index=True)

    # 1. Higienização das colunas de texto
    if colunas_texto:
        for col in colunas_texto.keys():
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
                
    # 2.Identifica e corrige colunas monetárias ou numéricas
    colunas_numericas = [c for c in df.columns if 'valor' in c.lower() or 'quantidade' in c.lower() or 'qtd' in c.lower()]
    for col in colunas_numericas:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
    # 3. Padronização geral de Strings (Colunas do tipo 'object' não numéricas)
    colunas_object = df.select_dtypes(include=['object']).columns
    for col in colunas_object:
        if colunas_texto and col in colunas_texto:
            continue 
        df[col] = df[col].fillna("").astype(str).str.strip()
        
    return df

def formatar_moeda(valor):
    """Formatador de valores monetarios"""
    try:
        if pd.isna(valor) or valor is None:
            return "0,00"
        val_float = float(valor)
        return f"{val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

def formatar_data(data_raw):
    """Formatação de dadas de forma geral"""
    try:
        if pd.isna(data_raw) or data_raw is None or str(data_raw).strip() == "":
            return "Não Informada"
            
        # Converte para string e isola apenas a data caso venha com timestamp (T00:00:00)
        data_str = str(data_raw).split('T')[0].strip()
        
        # Trata formato YYYY-MM-DD
        if '-' in data_str:
            partes = data_str.split('-')
            if len(partes) == 3:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
                
        # Trata formato YYYYMMDD puro que algumas APIs retornam
        elif len(data_str) == 8 and data_str.isdigit():
            return f"{data_str[6:8]}/{data_str[4:6]}/{data_str[0:4]}"
            
        return data_str
    except Exception:
        return "Não Informada"

def obter_caminho_arquivos(prefixo, ano, codigo_mun):
    """Retorna o caminhom especifico de cada parquet"""
    if codigo_mun == "Todos":
        return sorted(glob.glob(f"data/{prefixo}_{ano}_*.parquet") + glob.glob(f"data/{prefixo}_{ano}.parquet"))
    mensais = glob.glob(f"data/{prefixo}_{ano}_*_{codigo_mun}.parquet")
    anuais = glob.glob(f"data/{prefixo}_{ano}_{codigo_mun}.parquet")
    return sorted(mensais + anuais)

# ==============================================================================
# MOTOR GENÉRICO DE FILTRAGEM (Data-Driven)
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
# RENDERIZADOR DA PÁGINA
# =============================================================================
def render_consultation_page():
    st.header("🔍 Consulta Detalhada")

    # 1. Trava de Segurança de Estado
    for k in ["consulta_realizada", "df_resultado", "filtros_aplicados"]:
        if k not in st.session_state: 
            st.session_state[k] = False if k == "consulta_realizada" else (pd.DataFrame() if k == "df_resultado" else {})

    lista_municipios = carregar_municipios()
    opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}
    categorias_disponiveis = list(config_endpoints.keys())

    if not categorias_disponiveis:
        st.warning("⚠️ O arquivo endpoints.json não foi carregado corretamente.")
        return

    # 2. MOTOR HÍBRIDO DE INTERFACE (Monta a UI lendo o JSON)
    with st.expander("Opções de Filtro", expanded=not st.session_state.consulta_realizada):
        categoria_sel = st.selectbox("Tipo de Documento", categorias_disponiveis)
        config_atual = config_endpoints.get(categoria_sel, {})
        
        col_ini, col_fim, col_mun = st.columns(3)
        ano_inicial = col_ini.selectbox("Ano Inicial", anos, index=2)
        ano_final = col_fim.selectbox("Ano Final", anos, index=5)
        municipio_sel = col_mun.selectbox("Município", options=["Todos"] + list(opcoes_mun.keys()))
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(f"🎯 Filtros específicos para: **{categoria_sel}**")
        
        filtros_dinamicos = {}
        schema_unificado = list(config_atual.get("campos_ui", []))

        # Injeta colunas de texto como inputs de busca
        for col_id, col_label in config_atual.get("colunas_texto", {}).items():
            schema_unificado.append({
                "id": col_id, "label": f"🏷️ {col_label}", "tipo": "text", "placeholder": f"Digite {col_label.lower()}..."
            })

        if schema_unificado:
            cols_grid = st.columns(3)
            for i, campo in enumerate(schema_unificado):
                with cols_grid[i % 3]:
                    c_id, c_label, c_tipo = campo["id"], campo["label"], campo["tipo"]
                    if c_tipo == "select":
                        val = st.selectbox(c_label, campo["opcoes"])
                        if val != "TODOS": filtros_dinamicos[c_id] = val
                    elif c_tipo == "number":
                        val = st.number_input(c_label, value=int(campo.get("default", 0)), step=int(campo.get("step", 1)))
                        if val > 0: filtros_dinamicos[c_id] = val
                    elif c_tipo == "text":
                        val = st.text_input(c_label, placeholder=campo.get("placeholder", ""), key=f"dyn_{categoria_sel}_{c_id}").strip()
                        if val: filtros_dinamicos[c_id] = val
        else: st.write("*(Nenhum atributo avançado mapeado)*")

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
    # 3. DISPARO DA CONSULTA (O Controller)
    # ==============================================================================
    if btn_consultar and ano_inicial <= ano_final:
        with st.spinner(f"Processando bases de {categoria_sel}..."):
            prefixo = config_atual.get("prefixo")
            codigo_mun_busca = "Todos" if municipio_sel == "Todos" else opcoes_mun[municipio_sel]['codigo_municipio']

            dfs_anos = []
            liq_map, pag_map = {}, {}
            def get_col(df, nomes): return next((c for c in nomes if c in df.columns), None)

            if categoria_sel == "Notas de Empenho":
                df_liq_g, df_pg_g = pd.DataFrame(), pd.DataFrame()
                for a in range(int(ano_inicial), int(ano_final) + 1):
                    df_liq_g = pd.concat([df_liq_g, carregar_e_filtrar(obter_caminho_arquivos("liquidacoes", a, codigo_mun_busca))], ignore_index=True)
                    df_pg_g = pd.concat([df_pg_g, carregar_e_filtrar(obter_caminho_arquivos("notas_pagamentos", a, codigo_mun_busca))], ignore_index=True)
                
                if not df_liq_g.empty:
                    df_liq_g['ch'] = df_liq_g['codigo_municipio'].astype(str) + "_" + df_liq_g.get('exercicio_orcamento', '').astype(str) + "_" + df_liq_g['codigo_orgao'].astype(str) + "_" + df_liq_g['numero_empenho'].astype(str)
                    c_liq = get_col(df_liq_g, ['valor_bruto_nota_liquidacao', 'valor_liquidado', 'valor_bruto'])
                    if c_liq: liq_map = df_liq_g.groupby('ch')[c_liq].apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()).to_dict()

                if not df_pg_g.empty:
                    df_pg_g['ch'] = df_pg_g['codigo_municipio'].astype(str) + "_" + df_pg_g.get('exercicio_orcamento', '').astype(str) + "_" + df_pg_g['codigo_orgao'].astype(str) + "_" + df_pg_g['numero_empenho'].astype(str)
                    pag_map = df_pg_g.groupby('ch')['valor_nota_pagamento'].apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()).to_dict()

            for a in range(int(ano_inicial), int(ano_final) + 1):
                arquivos = obter_caminho_arquivos(prefixo, a, codigo_mun_busca)
                if not arquivos: continue
                    
                df_ano = carregar_e_filtrar(arquivos, colunas_texto=config_atual.get("colunas_texto", {}))
                if df_ano.empty: continue

                if municipio_sel != "Todos" and 'municipio_referencia' in df_ano.columns:
                    df_ano = df_ano[df_ano['municipio_referencia'].str.upper() == opcoes_mun[municipio_sel]['nome_municipio'].upper()]
                if df_ano.empty: continue

                df_ano['match_reason'] = ""
                if categoria_sel == "Notas de Empenho":
                    df_ano['ch'] = df_ano['codigo_municipio'].astype(str) + "_" + df_ano.get('exercicio_orcamento', str(a)).astype(str) + "_" + df_ano['codigo_orgao'].astype(str) + "_" + df_ano['numero_empenho'].astype(str)
                    df_ano['valor_liquidado'] = df_ano['ch'].map(liq_map).fillna(0.0)
                    df_ano['valor_pago'] = df_ano['ch'].map(pag_map).fillna(0.0)
                    df_ano['status_pagamento'] = df_ano.apply(lambda r: "PENDENTE" if float(r.get('valor_pago',0)) <= 0 else ("PAGO" if float(r.get('valor_pago',0)) >= float(r.get('valor_empenhado',0)) else "PARCIAL"), axis=1)

                dfs_anos.append(df_ano)

            df_consolidado = pd.concat(dfs_anos, ignore_index=True) if dfs_anos else pd.DataFrame()
            df_final = filtrar_dataframe(df_consolidado, filtros_dinamicos, filtro_geral, filtro_fornecedor, config_atual)

            st.session_state.df_resultado = df_final
            st.session_state.consulta_realizada = True
            st.session_state.filtros_aplicados = {
                "categoria_sel": categoria_sel, "ano_inicial": ano_inicial, "ano_final": ano_final,
                "municipio_sel": municipio_sel, "codigo_mun_busca": codigo_mun_busca, "prefixo": prefixo,
                "filtro_geral": filtro_geral, "filtro_fornecedor": filtro_fornecedor, **filtros_dinamicos
            }

    # ==============================================================================
    # 4. EXIBIÇÃO DOS RESULTADOS (Invocando o dynamic_card.py)
    # ==============================================================================
    if st.session_state.consulta_realizada:
        df = st.session_state.df_resultado
        filtros = st.session_state.filtros_aplicados
        
        st.subheader(f"LISTA DE {filtros['categoria_sel'].upper()} - {filtros['ano_inicial']} A {filtros['ano_final']}")
        if filtros['municipio_sel'] != "Todos": st.write(f"📍 Município: **{opcoes_mun[filtros['municipio_sel']]['nome_municipio']}**")
            
        if not df.empty:
            st.caption(f"Foram encontrados **{len(df):,}** registros.")

            # A RENDERIZAÇÃO LIMPA E DESACOPLADA:
            limite = 20
            for index, row in df.head(limite).iterrows():
                renderizar_card_dinamico(
                    row=row,
                    index=index,
                    categoria=filtros['categoria_sel'],
                    config_atual=config_endpoints.get(filtros['categoria_sel'], {}),
                    filtro_geral=filtros['filtro_geral'],
                    ano_inicial=filtros['ano_inicial'],
                    codigo_mun_busca=filtros['codigo_mun_busca']
                )

            if len(df) > limite: st.info(f"Exibindo os {limite} primeiros registros de alta relevância.")

            st.divider()
            st.markdown("### 📥 Opções de Exportação")
            
            csv_data = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label=f"📥 Exportar Grid Atual ({len(df):,} linhas)", 
                data=csv_data, 
                file_name=f"TCE_{filtros['prefixo']}_{filtros['ano_inicial']}_{filtros['ano_final']}.csv", 
                mime="text/csv", use_container_width=True
            )
            
            if filtros['categoria_sel'] == "Notas de Empenho":
                renderizar_botoes_exportacao(
                    df_empenhos_filtrados=df,
                    ano_inicial=filtros['ano_inicial'],
                    ano_final=filtros['ano_final'],
                    codigo_mun=filtros['codigo_mun_busca'],
                    obter_caminho_func=obter_caminho_arquivos_modal,
                    carregar_e_filtrar_func=carregar_e_filtrar_modal 
                )
        else:
            st.warning("Nenhum registro encontrado para os filtros aplicados.")
    else:
        st.info("Selecione os parâmetros acima e clique em 'Consultar' para carregar a base de dados.")