# ==========================================
    # UPLOAD DO DOCUMENTO E MOTOR OCR
    # ==========================================
    st.divider()
    st.subheader("2. Upload do Documento Físico ou Digital")
    
    # ⚠️ NOVIDADE: Adicionado suporte a pdf e txt
    arquivo_nf = st.file_uploader("Anexe o Documento (JPG, PNG, PDF ou TXT)", type=['jpg', 'jpeg', 'png', 'pdf', 'txt'])

    if arquivo_nf is not None:
        col_doc, col_analise = st.columns(2)
        extensao_arq = arquivo_nf.name.split('.')[-1].lower()

        with col_doc:
            st.markdown("#### Documento Original")
            
            # Adapta a exibição visual dependendo do tipo de arquivo
            if extensao_arq in ['jpg', 'jpeg', 'png']:
                imagem_exibicao = Image.open(arquivo_nf)
                st.image(imagem_exibicao, use_container_width=True)
            elif extensao_arq == 'pdf':
                st.info("📄 Arquivo PDF carregado com sucesso. A visualização nativa está desativada para preservar memória, mas o motor de leitura está processando as páginas.")
            elif extensao_arq == 'txt':
                st.info("📝 Arquivo de Texto carregado com sucesso.")

        with col_analise:
            st.markdown("#### Análise do Motor Híbrido")
            
            with st.spinner("Extraindo e processando dados estruturados..."):
                arquivo_nf.seek(0)
                
                # ⚠️ NOVIDADE: Chama o novo motor roteador
                from src.modules.ocr_engine import processar_documento 
                texto = processar_documento(arquivo_nf)
                resultado = auditar_dados_nf(texto)

            # --- MOTOR DE DECISÃO ---
            cnpj_ocr = resultado['cnpj_encontrado']
            valor_ocr = resultado['valor_total_encontrado']

            st.write("###### Parecer Automatizado:")
            
            if cnpj_ocr:
                cnpj_ocr_limpo = limpar_apenas_numeros(cnpj_ocr)
                cnpj_esperado_limpo = limpar_apenas_numeros(cnpj_esperado)
                
                if cnpj_ocr_limpo == cnpj_esperado_limpo:
                    st.success(f"✅ **CNPJ Validado:** Match perfeito com o fornecedor da API.")
                else:
                    st.error(f"❌ **Divergência de CNPJ!**\n\n**Lido:** {cnpj_ocr}\n**Base TCE:** {cnpj_esperado}")
            else:
                st.warning("⚠️ **CNPJ não localizado:** A qualidade do arquivo ou o formato impediram a leitura.")

            if valor_ocr is not None and not pd.isna(valor_esperado):
                if round(valor_ocr, 2) == round(valor_esperado, 2):
                    st.success(f"✅ **Valor Validado:** R$ {valor_ocr:,.2f}")
                else:
                    st.error(f"❌ **Divergência de Valor Financeiro!**\n\n**Lido:** R$ {valor_ocr:,.2f}\n**Base TCE:** R$ {valor_esperado:,.2f}")
            else:
                st.warning("⚠️ **Valor financeiro não localizado** ou valor nulo na base de dados.")
            
            with st.expander("Ver texto bruto extraído (Debug Engine)"):
                st.text(resultado['texto_bruto'])