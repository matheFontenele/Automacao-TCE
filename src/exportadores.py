import streamlit as st
import numpy as np
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

    # 6. Adição de colunas referentes a prazo e pagamentos
    dt_liqui = pd.to_datetime(df_consolidado.get('data_liquidacao'), errors='coerce')
    dt_pag = pd.to_datetime(df_consolidado.get('data_nota_pagamento'), errors='coerce')
    
    # Regra: Prazo limite para pagamento é de 30 dias após a liquidação
    df_consolidado['data_prevista_pagamento'] = (dt_liqui + pd.Timedelta(days=30)).dt.strftime('%Y-%m-%d')

    # Status de Finalização do Fluxo
    df_consolidado['status_execucao'] = np.where(
        dt_pag.notna(), 
        'FINALIZADO', 
        np.where(dt_liqui.notna(), 'PENDENTE (AGUARDANDO PAGAMENTO)', 'EMPENHADO (NÃO LIQUIDADO)')
    )

    # Cálculo dos Dias em Atraso
    hoje = pd.Timestamp.now().normalize()
    prazo_limite = dt_liqui + pd.Timedelta(days=30)

    # Dias decorridos se já pago VS se está pendente hoje
    atraso_se_pago = (dt_pag - prazo_limite).dt.days
    atraso_se_pendente = (hoje - prazo_limite).dt.days

    df_consolidado['dias_atraso'] = np.where(
        dt_pag.notna(),
        atraso_se_pago,
        np.where(dt_liqui.notna(), atraso_se_pendente, 0)
    )
    # Garante que se pagou antes do prazo, o atraso seja zero (não número negativo)
    df_consolidado['dias_atraso'] = df_consolidado['dias_atraso'].clip(lower=0).fillna(0).astype(int)

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

    # 6. Estrutura rígida de saída das colunas (Ordenação Cronológica e Intuitiva)
    colunas_solicitadas = [
        # ==============================================================================
        # 1. CONTEXTO E IDENTIFICAÇÃO (Onde e Quando?)
        # ==============================================================================
        'codigo_municipio', 
        'exercicio_orcamento', 
        'codigo_orgao', 
        'codigo_unidade',
        
        # ==============================================================================
        # 2. FASE DE EMPENHO (Quem comprou, o que comprou e quanto reservou?)
        # ==============================================================================
        'numero_empenho', 
        'data_emissao_empenho', 
        'data_referencia_empenho',
        'modalidade_empenho', 
        'codigo_elemento_despesa', 
        'nome_negociante', 
        'descricao_empenho',
        'valor_anterior_saldo_dotacao', 
        'valor_empenhado', 
        'valor_atual_saldo_dotacao',
        
        # ==============================================================================
        # 3. FASE DE LIQUIDAÇÃO E NOTA FISCAL (O serviço foi entregue? Cadê o documento?)
        # ==============================================================================
        'data_liquidacao', 
        'data_referencia_liquidacao', 
        'tipo_nota_fiscal', 
        'numero_nota_fiscal', 
        'data_emissao',             # Data de emissão da NF
        'valor_bruto', 
        'valor_desconto', 
        'valor_liquido', 
        'valor_liquidado', 
        'valor_base_calculo_iss', 
        'valor_aliquota_iss',
        
        # ==============================================================================
        # 4. FASE DE PAGAMENTO (O dinheiro saiu do banco?)
        # ==============================================================================
        'numero_nota_pagamento', 
        'data_nota_pagamento', 
        'data_referencia',          # Referência do pagamento
        'nu_documento_caixa', 
        'valor_nota_pagamento', 
        'valor_empenhado_a_pagar',
        
        # ==============================================================================
        # 5. AUDITORIA E MÉTRICAS DE CONTROLE (Qual a situação atual desse processo?)
        # ==============================================================================
        'status_execucao', 
        'data_prevista_pagamento', 
        'dias_atraso'
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

    col_json, col_xlsx = st.columns(2)

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

    with col_xlsx:
        try:
            with st.spinner("Compilando e cruzando dados relacionais da planilha..."):
                df_detalhado = gerar_dataframe_detalhado(
                    df_empenhos_filtrados, ano, codigo_mun, 
                    obter_caminho_func, carregar_e_filtrar_func
                )

                # 2. Aplica a estilização visual (Cores) nas colunas de controle do final do arquivo
                df_colorido = df_detalhado.style.set_properties(
                    **{'background-color': '#FFF2CC'}, # AMARELO
                    subset=['status_execucao', 'data_prevista_pagamento']
                ).set_properties(
                    **{'background-color': '#FCE4D6'}, # VERMELHO
                    subset=['dias_atraso']
                ).set_properties(
                    **{'background-color': '#DDEBF7'}, # AZUL
                    subset=['codigo_municipio', 'exercicio_orcamento', 'codigo_unidade', 'data_emissao_empenho']
                )
                
                # Conversão utilizando openpyxl para manter os estilos inseridos acima
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_colorido.to_excel(writer, index=False, sheet_name='Auditoria_TCE')
                
                # Correção aplicada aqui: Removido o 'mime' duplicado e adicionado o 'file_name' de saída
                st.download_button(
                    label="📊 Exportar Excel Detalhado (Relacional)",
                    data=excel_buffer.getvalue(),
                    file_name=f"auditoria_empenhos_{codigo_mun}_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Erro ao gerar Excel Detalhado: {e}")