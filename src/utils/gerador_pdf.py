# gerador_pdf.py
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==============================================================================
# FUNÇÕES DE FORMATAÇÃO EXCLUSIVAS DO RELATÓRIO
# ==============================================================================
def formatar_moeda_pdf(valor):
    try:
        if pd.isna(valor) or valor is None:
            return "0,00"
        val_float = float(valor)
        return f"{val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

def formatar_data_pdf(data_raw):
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

# ==============================================================================
# GERADOR DO PDF ATUALIZADO E REDIMENSIONADO
# ==============================================================================
def gerar_pdf_empenho(row, df_liq_filtrada=None, df_pag_filtrado=None):
    """Gera o PDF estruturado aproveitando 100% da largura útil disponível."""
    buffer = BytesIO()
    
    # Margens estreitas (10 pontos). Largura total útil = 612 - 20 = 592 pontos.
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=10, 
        leftMargin=10, 
        topMargin=10, 
        bottomMargin=10
    )
    story = []
    styles = getSampleStyleSheet()
    
    LARGURA_MAXIMA = 592  # Força as tabelas a irem até a borda da folha
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=13,
        leading=15,
        textColor=colors.HexColor('#ff4b4b'),
        spaceAfter=8
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#334155')
    )
    
    bold_style = ParagraphStyle(
        'TableBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    header_table_style = ParagraphStyle(
        'HeaderTable',
        parent=body_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1e293b')
    )

    story.append(Paragraph(f"TCE-CE — DETALHES DO EMPENHO Nº {row.get('numero_empenho', 'N/A')}", title_style))
    
    def criar_linha_tabela(label, valor):
        val_str = str(valor) if pd.notna(valor) and valor is not None else "Não informado"
        return [Paragraph(f"<b>{label}</b>", bold_style), Paragraph(val_str, body_style)]

    # Seção 1: Informações do Empenho
    story.append(Paragraph("INFORMAÇÕES DO EMPENHO", section_style))
    fornecedor = row.get('nome_negociante', row.get('nome_responsavel_pagamento', 'Não Informado'))
    cnpj_fornecedor = row.get('numero_documento_negociante', row.get('cpf_cnpj_emitente', 'Ocultado'))
    num_licitacao = row.get('numero_licitacao')
    num_licitacao_str = str(num_licitacao) if pd.notna(num_licitacao) else "Não informado"
    
    dados_empenho = [
        criar_linha_tabela("Número do empenho:", row.get('numero_empenho', 'N/A')),
        criar_linha_tabela("Data:", formatar_data_pdf(row.get('data_emissao_empenho'))),
        criar_linha_tabela("Valor:", f"R$ {formatar_moeda_pdf(row.get('valor_empenhado', 0.0))}"),
        criar_linha_tabela("Fornecedor:", fornecedor),
        criar_linha_tabela("CNPJ do fornecedor:", cnpj_fornecedor),
        criar_linha_tabela("Modalidade de licitação:", row.get('tipo_processo_licitatorio', 'N/A')),
        criar_linha_tabela("Número de licitação:", num_licitacao_str)
    ]
    
    # Redimensionado: 140 + 432 = 572 (Largura máxima)
    t_empenho = Table(dados_empenho, colWidths=[140, 432])
    t_empenho.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('PADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_empenho)

    # Seção 2: Informações de Orçamento
    story.append(Paragraph("INFORMAÇÕES DE ORÇAMENTO", section_style))
    unidade_gestora = row.get('nome_unidade_gestora', row.get('codigo_unidade_gestora', 'Não Informado'))
    proj_ativ = f"{row.get('codigo_projeto_atividade', '')}.{row.get('numero_projeto_atividade', '')}" if pd.notna(row.get('codigo_projeto_atividade')) else "Não informado"
    
    dados_orcamento = [
        criar_linha_tabela("Unidade gestora:", unidade_gestora),
        criar_linha_tabela("Órgão:", f"{row.get('codigo_orgao', 'N/A')} - {row.get('nome_orgao', 'Secretaria Municipal')}"[:90]),
        criar_linha_tabela("Unidade orçamentária:", row.get('codigo_unidade_orcamentaria', 'N/A')),
        criar_linha_tabela("Proj. atividade:", proj_ativ),
        criar_linha_tabela("Natureza:", row.get('descricao_elemento_despesa', 'N/A')[:90]),
        criar_linha_tabela("Função:", row.get('codigo_funcao', 'N/A')),
        criar_linha_tabela("Sub-função:", row.get('codigo_subfuncao', 'N/A')),
        criar_linha_tabela("Fonte de recurso:", row.get('fonte_recurso', 'Não Informada'))
    ]
    
    # Redimensionado: 140 + 432 = 572
    t_orcamento = Table(dados_orcamento, colWidths=[140, 432])
    t_orcamento.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('PADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_orcamento)

    # Seção 3: Histórico
    story.append(Paragraph("INFORMAÇÕES DO HISTÓRICO", section_style))
    hist_text = row.get('descricao_historico_empenho', 'Sem descrição adicional cadastrada.')
    t_historico = Table([[Paragraph(hist_text, body_style)]], colWidths=[LARGURA_MAXIMA])
    t_historico.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_historico)

    # ==============================================================================
    # SEÇÃO INTERMEDIÁRIA: LIQUIDAÇÕES (REDIMENSIONADA PARA 572)
    # ==============================================================================
    if df_liq_filtrada is not None and not df_liq_filtrada.empty:
        story.append(Paragraph("MOVIMENTAÇÕES DA LIQUIDAÇÃO", section_style))
        
        t_liq_dados = [[
            Paragraph("Data", header_table_style),
            Paragraph("Nº Liquidação", header_table_style),
            Paragraph("Valor", header_table_style)
        ]]
        
        col_data_liq = next((c for c in ['data_nota_liquidacao', 'data_liquidacao', 'data_emissao'] if c in df_liq_filtrada.columns), None)
        col_num_liq = next((c for c in ['numero_nota_liquidacao', 'numero_nota_fiscal', 'numero_documento'] if c in df_liq_filtrada.columns), None)
        col_valor_liq = next((c for c in ['valor_bruto_nota_liquidacao', 'valor_liquidado', 'valor_bruto', 'valor_nota_fiscal'] if c in df_liq_filtrada.columns), None)
        
        total_liq = 0.0
        for _, l_row in df_liq_filtrada.iterrows():
            d_val = formatar_data_pdf(l_row[col_data_liq]) if col_data_liq else "Não informada"
            n_val = str(l_row[col_num_liq]) if col_num_liq else str(l_row.get('numero_empenho', 'N/A'))
            
            v_raw = l_row[col_valor_liq] if col_valor_liq else 0.0
            try: total_liq += float(v_raw)
            except: pass
            v_val = f"R$ {formatar_moeda_pdf(v_raw)}"
            
            t_liq_dados.append([Paragraph(d_val, body_style), Paragraph(n_val, body_style), Paragraph(v_val, body_style)])
            
        t_liq_dados.append([
            Paragraph(f"<b>Quantidade: {len(df_liq_filtrada)}</b>", body_style), 
            Paragraph("", body_style), 
            Paragraph(f"<b>Total: R$ {formatar_moeda_pdf(total_liq)}</b>", bold_style)
        ])
        
        # Redimensionado: 130 + 282 + 160 = 572
        t_liq = Table(t_liq_dados, colWidths=[130, 282, 160])
        t_liq.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
            ('PADDING', (0,0), (-1,-1), 3),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_liq)

    # ==============================================================================
    # SEÇÃO INTERMEDIÁRIA: PAGAMENTOS (REDIMENSIONADA PARA 572)
    # ==============================================================================
    if df_pag_filtrado is not None and not df_pag_filtrado.empty:
        story.append(Paragraph("MOVIMENTAÇÕES DE PAGAMENTO", section_style))
        
        t_pag_dados = [[
            Paragraph("Data", header_table_style),
            Paragraph("Número Pagamento", header_table_style),
            Paragraph("Valor", header_table_style)
        ]]
        
        col_valor_pag = 'valor_nota_pagamento' if 'valor_nota_pagamento' in df_pag_filtrado.columns else 'valor_pago'
        
        total_pag = 0.0
        for _, p_row in df_pag_filtrado.iterrows():
            d_val = formatar_data_pdf(p_row.get('data_nota_pagamento'))
            n_val = str(p_row.get('numero_nota_pagamento', 'N/A'))
            
            v_raw = p_row[col_valor_pag] if col_valor_pag in df_pag_filtrado.columns else 0.0
            try: total_pag += float(v_raw)
            except: pass
            v_val = f"R$ {formatar_moeda_pdf(v_raw)}"
            
            t_pag_dados.append([Paragraph(d_val, body_style), Paragraph(n_val, body_style), Paragraph(v_val, body_style)])
            
        t_pag_dados.append([
            Paragraph(f"<b>Quantidade: {len(df_pag_filtrado)}</b>", body_style), 
            Paragraph("", body_style), 
            Paragraph(f"<b>Total: R$ {formatar_moeda_pdf(total_pag)}</b>", bold_style)
        ])
        
        # Redimensionado: 130 + 282 + 160 = 572
        t_pag = Table(t_pag_dados, colWidths=[130, 282, 160])
        t_pag.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
            ('PADDING', (0,0), (-1,-1), 3),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_pag)

    doc.build(story)
    buffer.seek(0)
    return buffer