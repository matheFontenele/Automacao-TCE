def gerar_tarefas(ano, municipio_selecionado, endpoints_alvo=None):
    """Gera tarefas dinamicamente lendo URLs, frequências e parâmetros do endpoints.json."""
    municipios = carregar_municipios()
    if municipio_selecionado:
        municipios = [m for m in municipios if m['codigo_municipio'] == municipio_selecionado['codigo_municipio']]

    lista_de_tarefas = []

    # 1. CARREGA A VERDADE UNIVERSAL (endpoints.json)
    try:
        with open('endpoints.json', 'r', encoding='utf-8') as f:
            config_json = json.load(f)
    except Exception as e:
        print(f"🚨 [EXTRACTION] Erro crítico ao ler endpoints.json: {e}")
        return []

    exercicio = int(f"{ano}00")

    # =========================================================================
    # FUNÇÃO AUXILIAR: Monta os parâmetros dinamicamente baseado no JSON
    # =========================================================================
    def montar_params(parametros_obrigatorios, codigo_mun, mes=None):
        """
        Constrói o dicionário de parâmetros da API a partir da lista de 
        parâmetros obrigatórios declarados no endpoints.json.
        """
        params = {
            "$format": "json",
            "$count": 1000,
            "$start_index": 0
        }
        
        for param in parametros_obrigatorios:
            if param == "exercicio_orcamento":
                params[param] = exercicio
            elif param == "codigo_municipio":
                params[param] = codigo_mun
            elif param == "data_referencia_doc":
                # Formato YYYYMM (ex: 202401, 202402...)
                if mes is not None:
                    params[param] = int(f"{ano}{str(mes).zfill(2)}")
            elif param == "data_inicio":
                params[param] = f"{ano}-01-01"
            elif param == "data_fim":
                params[param] = f"{ano}-12-31"
            # Adicione aqui novos parâmetros conforme forem surgindo
            # elif param == "outro_param":
            #     params[param] = ...
        
        return params

    # =========================================================================
    # 2. ITERA PELOS ENDPOINTS E GERA AS TAREFAS
    # =========================================================================
    for nome_display, meta in config_json.items():
        prefixo = meta.get("prefixo")
        url = meta.get("endpoint")
        freq = meta.get("frequencia", "mensal").lower().strip()
        parametros_obrigatorios = meta.get("parametros_obrigatorios", [])

        if not prefixo or not url:
            continue

        # FILTRO BLINDADO: Aceita prefixo OU nome de display
        if endpoints_alvo:
            if (prefixo not in endpoints_alvo) and (nome_display not in endpoints_alvo):
                continue

        # Validação: se não houver parâmetros obrigatórios, não gera tarefas
        if not parametros_obrigatorios:
            print(f"⚠️ [EXTRACTION] {nome_display} não tem 'parametros_obrigatorios' no JSON. Ignorando.")
            continue

        # Decide quantas iterações baseado na frequência
        iteracoes_mensais = range(1, 13) if freq == "mensal" else [None]

        for mes in iteracoes_mensais:
            for m in municipios:
                # Monta o nome do arquivo (com ou sem mês)
                if mes is not None:
                    caminho = os.path.join('data', f"{prefixo}_{ano}_{mes:02d}_{m['codigo_municipio']}.parquet")
                else:
                    caminho = os.path.join('data', f"{prefixo}_{ano}_{m['codigo_municipio']}.parquet")

                # Monta os parâmetros dinamicamente
                params = montar_params(parametros_obrigatorios, m['codigo_municipio'], mes)

                lista_de_tarefas.append({
                    'dataset_nome': prefixo,
                    'url': url,
                    'municipio_nome': m['nome_municipio'],
                    'ano_referencia': ano,
                    'params': params,
                    'caminho_arquivo': caminho
                })

    return lista_de_tarefas