import streamlit as st
import pandas as pd
import os
import glob
import re
import time
import requests
import threading
import concurrent.futures
import json
import datetime
from pathlib import Path
from tqdm import tqdm


# ==============================================================
# CONFIGURAÇÕES EXTRAS
# ==============================================================

PASTA_DADOS = "/app/data"

# Mapeamento para garantir que o nome da aba encontre o arquivo correto no disco
DATA_MAP = {
    "Notas de Empenho": "notas_empenho",
    "Notas Fiscais": "notas_fiscais",
    "Notas de Pagamento": "notas_pagamentos",
    "Pagamento e Liquidações": "pagamento_e_liquidacoes",
    "Liquidações": "liquidacoes",
    "Itens de Notas Fiscais": "itens_notas_fiscais",
    "Bens Incorporados ao Patrimônio": "bens_incorporados_patrimonio_municipio",
    "Controle de bens": "controle_besn_unidades_orcamentarias",
    "Ajuste, Reavaliação e Desincorporação": "ajuste_reavaliacao_patrimonial_desincorporacao_bem_municipio",
    "Contas Redutoras e Bens Incorporados": "contas_redutoras_bens_incorporados_patrimonio_municipio",
    "Controle de bens e notas de empenho": "controle_besn_notas_empenho"
}


# Carrega a lista de municípios do arquivo JSON para uso na geração das tarefas de extração
def carregar_municipios():
    """
    Carrega municípios do JSON da raiz do projeto
    """
    try:
        caminho_json = Path(__file__).resolve().parents[2] / 'municipios.json'
        
        if not caminho_json.exists():
            caminho_json = Path('/app/municipios.json')
        
        print(f"📂 Carregando JSON de: {caminho_json}")
        
        if not caminho_json.exists():
            print(f"🚨 ERRO: {caminho_json} não encontrado")
            print(f"📍 Diretório atual: {os.getcwd()}")
            return []
        
        with open(caminho_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ {len(data['elements'])} municípios carregados!")
        return data['elements']
        
    except Exception as e:
        print(f"🚨 ERRO: {type(e).__name__}: {e}")
        return []


# Função de logs terminal so que bonito, colorido e formatado para o terminal (Linux)
def formatar_log_terminal(msg: str) -> str:
    RESET = "\033[0m"
    VERDE = "\033[32m"
    AMARELO = "\033[33m"
    VERMELHO = "\033[31m"
    AZUL = "\033[34m"
    CYAN = "\033[36m"
    NEGRITO = "\033[1m"

    if "Iniciando extração" in msg or "Total de tarefas" in msg:
        return f"{AZUL}⚡ {msg}{RESET}"
        
    if "Resumo:" in msg:
        return f"\n{CYAN}{NEGRITO}📊 {msg}{RESET}\n"

    if "🚨 [ALERTA]" in msg:
        return f"{AMARELO}{NEGRITO}{msg}{RESET}"

    # 🟢 SUCESSO (Criado com sucesso)
    if "✅ Criado com sucesso:" in msg:
        conteudo = msg.replace("✅ Criado com sucesso:", "").strip()
        partes = conteudo.split(" ")
        nome_arq = partes[0]
        detalhes = " ".join(partes[1:]) if len(partes) > 1 else "Salvo."
        return f"{VERDE}│ 🟢 [SALVO]    │{RESET} {nome_arq:<65} {VERDE}│{RESET} {detalhes}"

    # 🟡 IGNORADO (Arquivo já existente)
    if "⏭️ Ignorado:" in msg:
        conteudo = msg.replace("⏭️ Ignorado:", "").replace("já existe.", "").strip()
        return f"{AMARELO}│ 🟡 [IGNORADO] │{RESET} {conteudo:<65} {AMARELO}│{RESET} Já em disco"

    # 🔵 VAZIO (Sem dados ou descartado por ano)
    if "⚠️ Vazio:" in msg:
        conteudo = msg.replace("⚠️ Vazio:", "").strip()
        partes = conteudo.split(" - ")
        nome_arq = partes[0]
        detalhes = partes[1] if len(partes) > 1 else "Sem registros no TCE"
        return f"{AZUL}│ 🔵 [VAZIO]    │{RESET} {nome_arq:<65} {AZUL}│{RESET} {detalhes}"

    # 🔴 FALHA (Tratamento dinâmico de erros de conexão/API)
    if "❌" in msg or "Erro" in msg:
        conteudo = msg.replace("❌", "").strip()
        nome_arq = "Erro de Processamento"
        detalhes = conteudo

        # Captura o nome do arquivo dinamicamente de dentro da mensagem de erro
        if "em " in conteudo:
            partes_em = conteudo.split("em ")
            detalhes = partes_em[0].strip()
            restante = partes_em[1].split(":")
            nome_arq = restante[0].strip()
            if len(restante) > 1:
                detalhes += " -> " + ":".join(restante[1:]).strip()
        elif "para " in conteudo:
            partes_para = conteudo.split("para ")
            detalhes = partes_para[0].strip()
            restante = partes_para[1].split(":")
            nome_arq = restante[0].strip()
            if len(restante) > 1:
                detalhes += " -> " + ":".join(restante[1:]).strip()

        # Encurta a mensagem técnica de SSL/EOF para manter o terminal scannable
        if "SSLEOFError" in detalhes or "Max retries exceeded" in detalhes:
            detalhes = "Conexão abortada pelo Firewall do TCE (SSL UNEXPECTED_EOF)"

        return f"{VERMELHO}│ 🔴 [FALHA]    │{RESET} {nome_arq:<65} {VERMELHO}│{RESET} {VERMELHO}{detalhes}{RESET}"

    return msg

# ==============================================================
# SISTEMA DE FILTROS E CONSULTA DE ARQUIVOS (OTIMIZADO)
# ==============================================================
def renderizar_aba_consulta(tipo_dado_selecionado):
    if not os.path.exists(PASTA_DADOS):
        st.warning(f"📂 O diretório `{PASTA_DADOS}` ainda não foi criado. Realize uma extração primeiro.")
        return

    # Lista arquivos guardados que começam com o prefixo correto do endpoint
    arquivos_disponiveis = [
        f for f in os.listdir(PASTA_DADOS) 
        if f.startswith(tipo_dado_selecionado) and f.endswith('.parquet')
    ]

    if not arquivos_disponiveis:
        st.warning(f"⚠️ Nenhum arquivo de de dados encontrado para este painel.")
        st.info("Configure os parâmetros na barra lateral e clique em 'Executar Extração'.")
        return

    # Extração reversa inteligente de metadados baseada no nome do arquivo
    anos = set()
    meses = set()
    municipios = set()

    for arq in arquivos_disponiveis:
        partes = arq.replace('.parquet', '').split('_')
        if len(partes) >= 3:
            anos.add(partes[-3])
            meses.add(partes[-2])
            municipios.add(partes[-1])

    st.markdown("### 🛠️ Filtros de Especificação")
    col1, col2, col3 = st.columns(3)

    with col1:
        ano_sel = st.selectbox("📅 Ano", ["Todos"] + sorted(list(anos)), key=f"ano_{tipo_dado_selecionado}")
    with col2:
        mes_sel = st.selectbox("📆 Mês", ["Todos"] + sorted(list(meses)), key=f"mes_{tipo_dado_selecionado}")
    with col3:
        mun_sel = st.selectbox("🏙️ Código Município", ["Todos"] + sorted(list(municipios)), key=f"mun_{tipo_dado_selecionado}")

    # Aplicação estruturada dos filtros na listagem
    arquivos_filtrados = arquivos_disponiveis
    if ano_sel != "Todos":
        arquivos_filtrados = [f for f in arquivos_filtrados if f.split('_')[-3] == ano_sel]
    if mes_sel != "Todos":
        arquivos_filtrados = [f for f in arquivos_filtrados if f.split('_')[-2] == mes_sel]
    if mun_sel != "Todos":
        arquivos_filtrados = [f for f in arquivos_filtrados if f.split('_')[-1].replace('.parquet', '') == mun_sel]

    st.divider()

    if arquivos_filtrados:
        st.success(f"🎯 Restam **{len(arquivos_filtrados)}** arquivos correspondentes aos filtros aplicados.")
        arquivo_final = st.selectbox("📄 Selecione o arquivo exato:", arquivos_filtrados, key=f"file_sel_{tipo_dado_selecionado}")
        
        caminho_completo = os.path.join(PASTA_DADOS, arquivo_final)
        
        if st.button(f"📊 Carregar e Visualizar Dados", use_container_width=True, type="primary", key=f"btn_{tipo_dado_selecionado}"):
            try:
                with st.spinner("Decodificando base Parquet de alta performance..."):
                    df = pd.read_parquet(caminho_completo)
                
                m1, m2 = st.columns(2)
                m1.metric("Total de Linhas", f"{len(df):,}".replace(",", "."))
                m2.metric("Total de Colunas", len(df.columns))
                
                st.markdown("### 📋 Tabela de Dados")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Download nativo convertido em tempo de execução
                st.download_button(
                    label="📥 Exportar Base Completa para CSV (Excel)",
                    data=df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig'),
                    file_name=arquivo_final.replace('.parquet', '.csv'),
                    mime='text/csv',
                    use_container_width=True,
                    key=f"dl_{tipo_dado_selecionado}"
                )
            except Exception as e:
                st.error(f"❌ Falha crítica ao ler arquivo de disco: {e}")
    else:
        st.error("❌ Nenhuma combinação encontrada para os filtros selecionados.")

# ==============================================================
# INICIO DE BLOCOS DE PROCESSAMENTO
# ==============================================================

# Cria um armazenamento local por thread para garantir isolamento e thread-safety
thread_local = threading.local()

def obter_sessao(forcar_nova=False):
    # Se forçado, deleta a sessão antiga do escopo local da Thread
    if forcar_nova and hasattr(thread_local, "session"):
        try:
            thread_local.session.close()
        except:
            pass
        delattr(thread_local, "session")

    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1)
        thread_local.session.mount('https://', adapter)
        
    return thread_local.session

# Função que processa cada tarefa individualmente, responsável por fazer a requisição, aplicar o filtro defensivo e salvar o arquivo parquet
def processar_lote(task):
    caminho_arquivo = task['caminho_arquivo']
    nome_arquivo = os.path.basename(caminho_arquivo)
    
    # Checkpoint: se o arquivo já existe, pula
    if os.path.exists(caminho_arquivo):
        return "IGNORADO", f"⏭️ Ignorado: {nome_arquivo} já existe."

    time.sleep(0.7)  # Pequena pausa para evitar picos de requisições em loops rápidos

    # Recupera a sessão persistente da thread atual
    session = obter_sessao()

    # Header amigável para evitar bloqueio por WAF/Firewall simples
    headers_requisicao = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Connection": "keep-alive"
    }

    try:
        todos_dados = []
        start_index = task['params'].get('$start_index', 0)
        count_limite = task['params'].get('$count', 1000)

        # 🔄 Loop de Paginação Ativa
        while True:
            task['params']['$start_index'] = start_index
            
            # 🛡️ Mini-loop de tolerância a falhas de rede/SSL (Backoff Exponencial)
            max_tentativas = 5
            response = None
            
            for tentativa in range(max_tentativas):
                try:
                    response = session.get(
                        task['url'], 
                        headers=headers_requisicao, 
                        params=task['params'], 
                        timeout=45
                    )
                    break  # Conectou com sucesso? Sai do loop de retentativa
                except (requests.exceptions.SSLError, requests.exceptions.RequestException) as e:
                    if tentativa == max_tentativas - 1:
                        return "ERRO_CONEXAO", f"❌ Derrubado pelo TCE após {max_tentativas} tentativas em {nome_arquivo}: {str(e)}"
                    
                    # Se deu erro de SSL/Conexão, fechamos a conexão atual para não travar o pool
                    # e forçamos o backoff exponencial mais agressivo
                    tempo_espera = (tentativa + 1) * 7
                    time.sleep(tempo_espera)
                    
                    # Recarrega uma sessão limpa caso a anterior tenha sido "sujada" pelo handshake quebrado
                    session = obter_sessao(forcar_nova=True)
            
            # Executa a validação se a resposta de rede foi bem-sucedida
            if response and response.status_code == 200:
                elementos = response.json().get("elements", [])
                if not elementos:
                    break  # Não vieram mais registros, interrompe o loop de paginação
                
                todos_dados.extend(elementos)
                
                # Se a API retornou menos que o limite, chegamos na última página
                if len(elementos) < count_limite:
                    break
                
                start_index += count_limite  # Avança o ponteiro para a próxima página
                time.sleep(0.5)  # Aumentado levemente para dar respiro ao servidor deles entre páginas
            else:
                status_atual = response.status_code if response is not None else "Sem Resposta"
                return "ERRO_API", f"❌ Erro na API para {nome_arquivo}: Status {status_atual}"

        if todos_dados:
            df = pd.DataFrame(todos_dados)
            
            # ==============================================================
            # 🛡️ FILTRO DEFENSIVO ADAPTADO
            # ==============================================================
            ano_esperado = str(task['ano_referencia'])
            if 'exercicio_orcamento' in df.columns:
                df['exercicio_orcamento_str'] = df['exercicio_orcamento'].astype(str)
                df = df[df['exercicio_orcamento_str'].str.startswith(ano_esperado)]
                df = df.drop(columns=['exercicio_orcamento_str'])
            
            if df.empty:
                return "VAZIO", f"⚠️ Vazio: {nome_arquivo} - Dados descartados por inconsistência de ano."
            # ==============================================================

            df['municipio_referencia'] = task['municipio_nome']
            df.to_parquet(caminho_arquivo, engine='pyarrow', compression='snappy')
            return "BAIXADO", f"✅ Criado com sucesso: {nome_arquivo} ({len(df)} linhas)"

        return "VAZIO", f"⚠️ Vazio: {nome_arquivo} - Sem registros no TCE."

    except Exception as e:
        return "ERRO_CONEXAO", f"❌ Erro inesperado em {nome_arquivo}: {str(e)}"

# Gera a lista de tarefas a partir dos filtros aplicados na interface do Streamlit
def gerar_tarefas(ano, municipio_selecionado, endpoints_alvo=None):
    """Gera tarefas dinamicamente focando em um único ano fechado (Janeiro a Dezembro)."""
    municipios = carregar_municipios()
    if municipio_selecionado:
        municipios = [m for m in municipios if m['codigo_municipio'] == municipio_selecionado['codigo_municipio']]

    lista_de_tarefas = []

    # Organização estrita dos endpoints do seu projeto
    endpoints_mensais = [
        ("notas_empenho", "https://api-dados-abertos.tce.ce.gov.br/sim/notas_empenhos"),
        ("notas_fiscais", "https://api-dados-abertos.tce.ce.gov.br/sim/notas_fiscais"),
        ("notas_pagamentos", "https://api-dados-abertos.tce.ce.gov.br/sim/notas_pagamentos"),
        ("pagamento_e_liquidacoes", "https://api-dados-abertos.tce.ce.gov.br/sim/pagamentos_liquidacoes"),
        ("liquidacoes", "https://api-dados-abertos.tce.ce.gov.br/sim/liquidacoes"),
        ("controle_besn_unidades_orcamentarias", "https://api-dados-abertos.tce.ce.gov.br/sim/controle_bens_unidades_orcamentarias"),
        ("ajuste_reavaliacao_patrimonial_desincorporacao_bem_municipio", "https://api-dados-abertos.tce.ce.gov.br/sim/ajuste_reavaliacao_patrimonial_desincorporacao_bem_municipio"),
        ("controle_besn_notas_empenho", "https://api-dados-abertos.tce.ce.gov.br/sim/controle_bens_notas_empenhos"),
        ("contas_redutoras_bens_incorporados_patrimonio_municipio", "https://api-dados-abertos.tce.ce.gov.br/sim/contas_redutoras_bens_incorporados_patrimonio_municipio")
    ]
    
    endpoints_anuais = [("itens_notas_fiscais", "https://api-dados-abertos.tce.ce.gov.br/sim/itens_notas_fiscais")]
    endpoints_intervalo_data = [("bens_incorporados_patrimonio_municipio", "https://api-dados-abertos.tce.ce.gov.br/sim/bens_incorporados_patrimonio_municipio")]

    # Filtra os endpoints antes de rodar os loops pesados
    if endpoints_alvo:
        endpoints_mensais = [e for e in endpoints_mensais if e[0] in endpoints_alvo]
        endpoints_anuais = [e for e in endpoints_anuais if e[0] in endpoints_alvo]
        endpoints_intervalo_data = [e for e in endpoints_intervalo_data if e[0] in endpoints_alvo]

    # Variável padrão utilizada pela API do TCE
    exercicio = int(f"{ano}00")

    # 1. Montagem das Tarefas Mensais (Itera fixo de 1 a 12 para o ano informado)
    if endpoints_mensais:
        for mes in range(1, 13):
            data_ref = int(f"{ano}{str(mes).zfill(2)}")
            for nome, url in endpoints_mensais:
                for m in municipios:
                    caminho = os.path.join('data', f"{nome}_{ano}_{mes:02d}_{m['codigo_municipio']}.parquet")
                    lista_de_tarefas.append({
                        'dataset_nome': nome, 'url': url, 'municipio_nome': m['nome_municipio'],
                        'ano_referencia': ano,
                        'params': {
                            "exercicio_orcamento": exercicio, "data_referencia_doc": data_ref, 
                            "$format": "json", "codigo_municipio": m['codigo_municipio'],
                            "$count": 1000, "$start_index": 0
                        },
                        'caminho_arquivo': caminho
                    })

    # 2. Montagem das Tarefas Anuais
    if endpoints_anuais:
        for nome, url in endpoints_anuais:
            for m in municipios:
                caminho = os.path.join('data', f"{nome}_{ano}_{m['codigo_municipio']}.parquet")
                lista_de_tarefas.append({
                    'dataset_nome': nome, 'url': url, 'municipio_nome': m['nome_municipio'],
                    'ano_referencia': ano,
                    'params': {
                        "exercicio_orcamento": exercicio, "$format": "json", 
                        "codigo_municipio": m['codigo_municipio'], "$count": 1000, "$start_index": 0
                    },
                    'caminho_arquivo': caminho
                })
            
    # 3. Montagem das Tarefas por Intervalo Customizado (Bens Incorporados travado no ano)
    if endpoints_intervalo_data:
        data_inicio_str = f"{ano}-01-01"
        data_fim_str = f"{ano}-12-31"

        for data, url in endpoints_intervalo_data:
            for m in municipios:
                caminho = os.path.join('data', f"{data}_{ano}_{m['codigo_municipio']}.parquet")
                lista_de_tarefas.append({
                    'dataset_nome': data, 'url': url, 'municipio_nome': m['nome_municipio'],
                    'ano_referencia': ano,
                    'params': {
                        'codigo_municipio': m['codigo_municipio'], 'data_inicio': data_inicio_str, 
                        'data_fim': data_fim_str, '$format': 'json', '$count': 1000, '$start_index': 0
                    },
                    'caminho_arquivo': caminho
                })

    return lista_de_tarefas

# Renderiza a página de extração no Streamlit, com os controles de filtro e a área de logs
def executar_pipeline(ano, municipio_selecionado=None, endpoints_alvo=None, log_func=print):
    os.makedirs('data', exist_ok=True)

    # Ajustado para refletir o ano único nos logs
    periodo_str = f"Ano {ano}"

    log_func(f"[{periodo_str}] Iniciando extração...")

    # 1. Gera as tarefas já filtradas na origem focado no ano informado
    tarefas = gerar_tarefas(ano, municipio_selecionado, endpoints_alvo=endpoints_alvo)
    
    if not tarefas:
        log_func(f"[{periodo_str}] Nenhuma tarefa encontrada para os filtros selecionados.")
        return

    log_func(f"[{periodo_str}] Total de tarefas a processar: {len(tarefas)}")

    baixados = 0
    ignorados = 0
    erros = 0
    
    # Execução Paralela Monitorada (Thread-Safe para Streamlit)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futuros = {executor.submit(processar_lote, tarefa): tarefa for tarefa in tarefas}
        pbar = tqdm(concurrent.futures.as_completed(futuros), total=len(tarefas), desc=f"Baixando {periodo_str}")
        
        erros_consecutivos = 0  
        
        for futuro in pbar:
            try:
                status, msg_log = futuro.result()
                
                # --- LÓGICA DE PROTEÇÃO: Monitoramento de falhas ---
                if status == "ERRO_CONEXAO" or "Status 429" in msg_log:
                    erros_consecutivos += 1
                else:
                    erros_consecutivos = 0  # Reseta se o processo teve sucesso ou foi ignorado
                
                # Se atingir o limite de falhas, pausa para resfriar a conexão
                if erros_consecutivos >= 15: 
                    log_func("🚨 [ALERTA] Muitos erros detectados. Pausando por 30s para evitar bloqueio...")
                    time.sleep(30)
                    erros_consecutivos = 0 # Reseta após a pausa
                # ----------------------------------------------------

                # Lógica original de log
                if log_func.__name__ == "log_colorido_terminal":
                    log_func(msg_log)
                elif log_func == print:
                    pbar.write(msg_log)
                else:
                    log_func(msg_log)
                
                if status == "BAIXADO":
                    baixados += 1
                elif status == "IGNORADO":
                    ignorados += 1
                else:
                    erros += 1
            except Exception as e:
                msg_falha = f"❌ Erro crítico no processamento de uma thread: {e}"
                pbar.write(msg_falha) if log_func == print else log_func(msg_falha)
                erros += 1
                erros_consecutivos += 1 

        log_func(f"[{periodo_str}] Resumo: {baixados} novos, {ignorados} já existiam, {erros} falhas/vazios.")

def render_extraction_page():
    # --- INICIALIZAÇÃO DO ESTADO GLOBAL DOS LOGS E ARQUIVOS ---
    if 'log_messages' not in st.session_state:
        st.session_state.log_messages = []
    if 'arquivos_criados' not in st.session_state:
        st.session_state.arquivos_criados = []

    # --- SIDEBAR (CONFIGURAÇÕES) ---
    with st.sidebar:
        st.header("Configurações")
        
        # 1. Seletor de Ano Único (Substituindo o antigo range de datas)
        hoje = datetime.date.today()
        ano_selecionado = st.number_input(
            "Ano de Referência",
            min_value=2008,
            max_value=2026,
            value=hoje.year,
            step=1
        )

        # 2. Seletor de Município
        lista_municipios = carregar_municipios()
        opcoes_mun = {f"{m['nome_municipio']} ({m['codigo_municipio']})": m for m in lista_municipios}
        
        if 'mun_input' not in st.session_state: 
            st.session_state.mun_input = "Todos"
        
        st.session_state.mun_input = st.selectbox(
            "Município", 
            options=["Todos"] + list(opcoes_mun.keys())
        )

        # 3. Multiselect de opções de dados
        st.subheader("Tipo de Dado")
        tipo_escolhido = st.selectbox(
            "Selecione a tabela:",
            options=list(DATA_MAP.keys())
        )

        endpoints_alvo = [DATA_MAP[tipo_escolhido]]

        # Botão para Executar a Extração
        btn_extrair = st.button("Executar Extração", use_container_width=True)

        # --- ÁREA DE LOGS E ARQUIVOS CRIADOS NA SIDEBAR ---
        log_placeholder = st.empty()

        if btn_extrair:
            # Reseta os logs e a lista de arquivos criados
            st.session_state.log_messages = []
            st.session_state.arquivos_criados = []
            
            # Marca o timestamp de início para sabermos quais arquivos foram criados NESTA rodada
            inicio_extracao = time.time()
            
            # Função de callback chamada pelo pipeline
            def stream_log(msg):
                st.session_state.log_messages.append(msg)
                
                # Monitora a pasta 'data' em busca de novos arquivos parquet criados após o início_extracao
                arquivos_atuais = []
                if os.path.exists('data'):
                    for f in glob.glob(os.path.join('data', '*.parquet')):
                        if os.path.getmtime(f) >= inicio_extracao:
                            nome_arq = os.path.basename(f)
                            if nome_arq not in arquivos_atuais:
                                arquivos_atuais.append(nome_arq)
                
                st.session_state.arquivos_criados = sorted(arquivos_atuais)

                # Atualiza a interface gráfica em tempo real
                with log_placeholder.container():
                    st.caption("🪵 Logs de Extração (Tempo Real)")
                    st.code("\n".join(st.session_state.log_messages[-50:]), language="text")
                    
                    if st.session_state.arquivos_criados:
                        st.caption("📁 Arquivos criados no disco:")
                        for arq in st.session_state.arquivos_criados:
                            st.markdown(f"🔹 `{arq}`")

            municipio_selecionado = None if st.session_state.mun_input == "Todos" else opcoes_mun[st.session_state.mun_input]
            
            with st.spinner(f"Buscando {tipo_escolhido} (Ano {ano_selecionado}) no TCE..."):
                try:
                    # 🚀 CHAMADA ATUALIZADA: Passa o parâmetro 'ano' de forma direta
                    executar_pipeline(
                        ano=int(ano_selecionado), 
                        municipio_selecionado=municipio_selecionado,
                        endpoints_alvo=endpoints_alvo, 
                        log_func=stream_log
                    )
                    st.success("Extração concluída com sucesso!")
                except Exception as e:
                    st.error(f"Erro durante a extração: {e}")
        
        # Mantém visível os logs e arquivos da última extração se o usuário navegar pelo app
        elif st.session_state.log_messages:
            with log_placeholder.container():
                if st.session_state.arquivos_criados:
                    st.subheader("📁 Últimos Arquivos Salvos")
                    for arq in st.session_state.arquivos_criados:
                        st.markdown(f"✅ `{arq}`")
                    st.divider()

                with st.expander("🪵 Ver Histórico de Logs", expanded=False):
                    st.code("\n".join(st.session_state.log_messages), language="text")
                    if st.button("Limpar Logs e Histórico", key="clear_logs"):
                        st.session_state.log_messages = []
                        st.session_state.arquivos_criados = []
                        st.rerun()

    # --- ÁREA PRINCIPAL ---
    st.header("Visualizar Dados")

    def carregar_e_exibir_dados(tipo_arquivo_prefixo):
        pasta_dados = 'data'
    
        if not os.path.exists(pasta_dados):
            st.warning(f"📂 O diretório `{pasta_dados}` ainda não foi criado. Realize uma extração primeiro.")
            return

        # Filtra apenas os arquivos que começam com o tipo de dado atual
        arquivos_disponiveis = [
            f for f in os.listdir(pasta_dados) 
            if f.startswith(tipo_arquivo_prefixo) and f.endswith('.parquet')
        ]

        if not arquivos_disponiveis:
            st.warning(f"⚠️ Nenhum arquivo de `{tipo_arquivo_prefixo}` encontrado no disco.")
            st.info("Configure os parâmetros na barra lateral e clique em 'Executar Extração'.")
            return

        # Extração reversa inteligente de metadados baseada no nome do arquivo
        anos = set()
        meses = set()
        municipios = set()

        for arq in arquivos_disponiveis:
            partes = arq.replace('.parquet', '').split('_')
            if len(partes) >= 3:
                # Identifica a posição dos metadados independente do tamanho do prefixo
                anos.add(partes[-3])
                meses.add(partes[-2])
                municipios.add(partes[-1])

        # Bloco Visual de Filtros Lado a Lado
        col1, col2, col3 = st.columns(3)

        with col1:
            ano_sel = st.selectbox("📅 Ano", ["Todos"] + sorted(list(anos)), key=f"ano_{tipo_arquivo_prefixo}")
        with col2:
            mes_sel = st.selectbox("📆 Mês", ["Todos"] + sorted(list(meses)), key=f"mes_{tipo_arquivo_prefixo}")
        with col3:
            mun_sel = st.selectbox("🏙️ Código Município", ["Todos"] + sorted(list(municipios)), key=f"mun_{tipo_arquivo_prefixo}")

        # Aplicação estruturada dos filtros na listagem
        arquivos_filtrados = arquivos_disponiveis
        if ano_sel != "Todos":
            arquivos_filtrados = [f for f in arquivos_filtrados if f.split('_')[-3] == ano_sel]
        if mes_sel != "Todos":
            arquivos_filtrados = [f for f in arquivos_filtrados if f.split('_')[-2] == mes_sel]
        if mun_sel != "Todos":
            arquivos_filtrados = [f for f in arquivos_filtrados if f.split('_')[-1].replace('.parquet', '') == mun_sel]

        st.divider()

        # Exibição do resultado filtrado
        if arquivos_filtrados:
            st.success(f"🎯 Encontrado(s) **{len(arquivos_filtrados)}** arquivo(s) correspondente(s) aos filtros.")
            
            # --- NOVO: LÓGICA DE SELEÇÃO MÚLTIPLA E MESCLAGEM ---
            col_chk, _ = st.columns([1, 1])
            with col_chk:
                selecionar_todos = st.checkbox("✅ Selecionar todos os arquivos filtrados", value=False, key=f"chk_all_{tipo_arquivo_prefixo}")
            
            if selecionar_todos:
                arquivos_selecionados = arquivos_filtrados
                st.info(f"📦 Todos os **{len(arquivos_filtrados)}** arquivos foram selecionados automaticamente.")
            else:
                arquivos_selecionados = st.multiselect(
                    "📄 Selecione os arquivos que deseja mesclar:", 
                    options=arquivos_filtrados,
                    default=None,
                    key=f"multi_{tipo_arquivo_prefixo}"
                )
            
            # Botão de ação destacado para carregar e concatenar os dataframes
            if arquivos_selecionados:
                botao_label = f"📊 Carregar e Mesclar {len(arquivos_selecionados)} arquivo(s)"
                
                if st.button(botao_label, use_container_width=True, type="primary", key=f"btn_{tipo_arquivo_prefixo}"):
                    try:
                        with st.spinner("Decodificando e concatenando bases Parquet de alta performance..."):
                            lista_dfs = []
                            
                            # Itera por cada arquivo selecionado, lê e joga na lista
                            for arquivo in arquivos_selecionados:
                                caminho_completo = os.path.join(pasta_dados, arquivo)
                                df_individual = pd.read_parquet(caminho_completo)
                                
                                # Garante que não vai quebrar se algum parquet estiver vazio por acidente
                                if not df_individual.empty:
                                    lista_dfs.append(df_individual)
                            
                            if lista_dfs:
                                # Junta tudo em um único DataFrame gigante mantendo o padrão das colunas
                                df_final = pd.concat(lista_dfs, ignore_index=True)
                                
                                # Exibe métricas rápidas consolidadas
                                m1, m2 = st.columns(2)
                                m1.metric("Total de Linhas Combinadas", f"{len(df_final):,}".replace(",", "."))
                                m2.metric("Total de Colunas", len(df_final.columns))
                                
                                st.markdown("### 📋 Tabela de Dados Combinada (Amostra)")
                                st.dataframe(df_final, use_container_width=True, hide_index=True)
                                
                                # Define um nome inteligente e limpo para o arquivo de download
                                nome_download = f"consolidado_{tipo_arquivo_prefixo}"
                                if ano_sel != "Todos": nome_download += f"_{ano_sel}"
                                if mun_sel != "Todos": nome_download += f"_{mun_sel}"
                                nome_download += ".csv"
                                
                                # Download nativo do CSV unificado convertido em tempo de execução
                                st.download_button(
                                    label="📥 Exportar Base unificada para CSV (Excel)",
                                    data=df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig'),
                                    file_name=nome_download,
                                    mime='text/csv',
                                    use_container_width=True,
                                    key=f"dl_{tipo_arquivo_prefixo}"
                                )
                            else:
                                st.warning("⚠️ Os arquivos selecionados estavam sem registros válidos para combinar.")
                                
                    except Exception as e:
                        st.error(f"❌ Erro crítico ao processar/mesclar os arquivos Parquet: {e}")
            else:
                st.info("💡 Escolha os arquivos acima ou marque 'Selecionar todos os arquivos filtrados' para gerar a exportação unificada.")
        else:
            st.error("❌ Nenhum arquivo encontrado para a combinação de filtros selecionada.")

    # Criação dinâmica das abas na área principal do app
    abas = st.tabs(list(DATA_MAP.keys()))
    
    for i, name_tab in enumerate(DATA_MAP.keys()):
        with abas[i]:
            # Invoca a nova lógica de filtros acoplada para cada dataset correspondente
            carregar_e_exibir_dados(DATA_MAP[name_tab])