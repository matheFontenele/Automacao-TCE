import streamlit as st
import pandas as pd
import io

def normalizar_coluna_chave(df, coluna):
    """Garante que as chaves de cruzamento estejam limpas e padronizadas."""
    if df.empty or coluna not in df.columns:
        return df
    df[coluna] = (
        df[coluna].astype(str)
        .str.strip()
        .str.replace(r'\.0$', '', regex=True)
        .str.replace(r'^0+', '', regex=True)
    )
    return df

def gerar_dataframe_detalhado(df_empenhos_filtrados, ano, codigo_mun, obter_caminho_func, carregar_e_filtrar_func):
    """
    Gera o DataFrame detalhado combinando empenhos, liquidações/notas fiscais e pagamentos
    de forma sequencial (alinhada), evitando a explosão de linhas por produto cartesiano.
    """
    if df_empenhos_filtrados is None or df_empenhos_filtrados.empty:
        return pd.DataFrame()

    # 1. Carregar bases correlatas
    arq_fiscais = obter_func_segura(obter_caminho_func, "notas_fiscais", ano, codigo_mun)
    if not arq_fiscais:
        arq_fiscais = obter_func_segura(obter_caminho_func, "liquidacoes", ano, codigo_mun)
        
    arq_pag = obter_func_segura(obter_caminho_func, "notas_pagamentos", ano, codigo_mun)

    df_nf = carregar_e_filtrar_func(arq_fiscais)
    df_pag = carregar_e_filtrar_func(arq_pag)

    # Chaves primárias de agrupamento do TCE-CE
    chaves = ['numero_empenho', 'codigo_municipio', 'codigo_orgao']

    # 2. Normalizar chaves para string limpa em todos os DataFrames
    lista_dfs = [df_empenhos_filtrados, df_nf, df_pag]
    for df_temp in lista_dfs:
        if df_temp is not None and not df_temp.empty:
            for c in chaves:
                if c in df_temp.columns:
                    df_temp[c] = df_temp[c].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.replace(r'^0+', '', regex=True)

    # 3. Criar sequenciadores para alinhar 1-para-1 os movimentos de cada empenho
    if df_nf is not None and not df_nf.empty:
        # Ordena por data e número da nota para garantir consistência cronológica
        cols_sort_nf = [c for c in ['data_liquidacao', 'numero_nota_fiscal'] if c in df_nf.columns]
        if cols_sort_nf:
            df_nf = df_nf.sort_values(by=chaves + cols_sort_nf)
        df_nf['seq_mov'] = df_nf.groupby(chaves).cumcount()
    else:
        df_nf = pd.DataFrame(columns=chaves + ['seq_mov'])

    if df_pag is not None and not df_pag.empty:
        cols_sort_pag = [c for c in ['data_nota_pagamento', 'numero_nota_pagamento'] if c in df_pag.columns]
        if cols_sort_pag:
            df_pag = df_pag.sort_values(by=chaves + cols_sort_pag)
        df_pag['seq_mov'] = df_pag.groupby(chaves).cumcount()
    else:
        df_pag = pd.DataFrame(columns=chaves + ['seq_mov'])

    # 4. Unir os movimentos (Liquidações + Pagamentos) pelo sequencial primeiro
    df_movimentos = pd.merge(df_nf, df_pag, on=chaves + ['seq_mov'], how='outer', suffixes=('_nf', '_pag'))

    # 5. Cruzar a estrutura de movimentos de volta com os cabeçalhos dos Empenhos
    df_consolidado = pd.merge(df_empenhos_filtrados, df_movimentos, on=chaves, how='left')

    # ==============================================================================
    # MAREAMENTO E TRATAMENTO DE SINÔNIMOS DOS CAMPOS SOLICITADOS
    # ==============================================================================
    if 'codigo_unidade_orcamentaria' in df_consolidado.columns:
        df_consolidado['codigo_unidade'] = df_consolidado['codigo_unidade_orcamentaria']
    if 'modalidade_nota_empenho' in df_consolidado.columns:
        df_consolidado['modalidade_empenho'] = df_consolidado['modalidade_nota_empenho']
    if 'descricao_historico_empenho' in df_consolidado.columns:
        df_consolidado['descricao_empenho'] = df_consolidado['descricao_historico_empenho']
    if 'data_referencia_doc' in df_consolidado.columns:
        df_consolidado['data_referencia_empenho'] = df_consolidado['data_referencia_doc']

    # Tratamento de datas e referências das liquidações incorporadas
    if 'data_referencia_doc_nf' in df_consolidado.columns:
        df_consolidado['data_referencia_liquidacao'] = df_consolidado['data_referencia_doc_nf']
    elif 'data_referencia_doc' in df_consolidado.columns:
        df_consolidado['data_referencia_liquidacao'] = df_consolidado['data_referencia_doc']

    df_consolidado['valor_liquidado'] = df_consolidado.get('valor_bruto', 0.0)

    # Tratamento de dados vindos da tabela de Pagamentos
    if 'data_referencia_pag' in df_consolidado.columns:
        df_consolidado['data_referencia'] = df_consolidado['data_referencia_pag']
    if 'numero_documento_caixa' in df_consolidado.columns:
        df_consolidado['nu_documento_caixa'] = df_consolidado['numero_documento_caixa']

    # 6. Estrutura rígida de saída das 30 colunas
    colunas_solicitadas = [
        # Base Empenho
        'codigo_municipio', 'exercicio_orcamento', 'codigo_orgao', 'codigo_unidade',
        'data_emissao_empenho', 'numero_empenho', 'data_referencia_empenho',
        'codigo_elemento_despesa', 'modalidade_empenho', 'descricao_empenho',
        'valor_anterior_saldo_dotacao', 'valor_empenhado', 'valor_atual_saldo_dotacao',
        'nome_negociante'
        # Base Pagamento
        'numero_nota_pagamento', 'data_referencia', 'nu_documento_caixa',
        'data_nota_pagamento', 'valor_nota_pagamento', 'valor_empenhado_a_pagar',
        # Base Notas Fiscais
        'tipo_nota_fiscal', 'numero_nota_fiscal', 'data_emissao', 'valor_liquido',
        'valor_desconto', 'valor_bruto', 'valor_aliquota_iss', 'valor_base_calculo_iss',
        # Base Liquidações
        'data_liquidacao', 'data_referencia_liquidacao', 'valor_liquidado'
    ]

    # Preenche colunas ausentes com None para evitar KeyErrors
    for col in colunas_solicitadas:
        if col not in df_consolidado.columns:
            df_consolidado[col] = None

    return df_consolidado[colunas_solicitadas]


def obter_func_segura(func, prefixo, ano, codigo_mun):
    """Garante execução amigável da função de glob sem travar o app."""
    try:
        return func(prefixo, ano, codigo_mun)
    except:
        return []


def renderizar_botoes_exportacao(df_empenhos_filtrados, ano, codigo_mun, obter_caminho_func, carregar_e_filtrar_func):
    """Gera a interface visual dos botões lado a lado no Streamlit."""
    if df_empenhos_filtrados.empty:
        return

    col_json, col_csv = st.columns(2)

    with col_json:
        try:
            # Drop de chaves internas criadas na grid antes de converter para JSON puro
            df_json_limpo = df_empenhos_filtrados.copy()
            colunas_remover = ['chave_composta', 'match_reason', 'status_pagamento']
            df_json_limpo = df_json_limpo.drop(columns=[c for c in colunas_remover if c in df_json_limpo.columns])
            
            json_string = df_json_limpo.to_json(orient="records", indent=4, force_ascii=False)
            st.download_button(
                label="📦 Exportar Grid em JSON",
                data=json_string,
                file_name=f"empenhos_export_{codigo_mun}_{ano}.json",
                mime="application/json",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erro ao gerar JSON: {e}")

    with col_csv:
        try:
            with st.spinner("Compilando e cruzando dados relacionais da planilha..."):
                df_detalhado = gerar_dataframe_detalhado(
                    df_empenhos_filtrados, ano, codigo_mun, 
                    obter_caminho_func, carregar_e_filtrar_func
                )
                
                # Conversão com o buffer em utf-8-sig para abrir direto no Excel em português sem quebrar acentos
                csv_buffer = io.StringIO()
                df_detalhado.to_csv(csv_buffer, index=False, sep=";", encoding="utf-8-sig")
                
                st.download_button(
                    label="📊 Exportar CSV Detalhado (Relacional)",
                    data=csv_buffer.getvalue(),
                    file_name=f"detalhado_empenhos_{codigo_mun}_{ano}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Erro ao gerar CSV Detalhado: {e}")