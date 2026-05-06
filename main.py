import os
import sys
import requests
import pandas as pd
import concurrent.futures
import json
from tqdm import tqdm 

# --- CONFIGURAÇÕES GERAIS ---
def carregar_municipios():
    with open('municipios.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['elements']

# Função de processamento em lote
def processar_lote(task):
    dataset_nome = task['dataset_nome']
    url = task['url']
    params = task['params']
    caminho_arquivo = task['caminho_arquivo']
    municipio_nome = task['municipio_nome']

    # CHECKPOINT: Se já existe, não baixa novamente
    if os.path.exists(caminho_arquivo):
        return None # Retorna None para não poluir o tqdm

    try:
        response = requests.get(url, headers={"Accept": "application/json"}, params=params, timeout=30)
        
        if response.status_code == 200:
            dados = response.json().get("elements", [])
            
            if dados:
                for item in dados:
                    item['municipio_referencia'] = municipio_nome
                
                df = pd.DataFrame(dados)
                # Salva em Parquet
                df.to_parquet(caminho_arquivo, engine='pyarrow', compression='snappy')
                return True
            else:
                return False # Vazio
        else:
            return False # Erro
            
    except Exception:
        return False # Falha

# Função Principal
def executar_pipeline(ano, mes_selecionado=None, municipio_selecionado=None, log_func=print):
    municipios = carregar_municipios()
    os.makedirs('data', exist_ok=True)
    
    exercicio = int(f"{ano}00")
    lista_de_tarefas = []

    if mes_selecionado == "Todos":
        mes_selecionado = None
        
    if municipio_selecionado == "Todos":
        municipio_selecionado = None

    # 1. Endpoints Mensais (precisam de mês)
    endpoints_mensais = [
        ("Notas de Empenho", "https://api-dados-abertos.tce.ce.gov.br/sim/notas_empenhos"),
        ("Notas Fiscais", "https://api-dados-abertos.tce.ce.gov.br/sim/notas_fiscais"),
        ("Notas de Pagamento", "https://api-dados-abertos.tce.ce.gov.br/sim/notas_pagamentos"),
        ("Liquidações", "https://api-dados-abertos.tce.ce.gov.br/sim/pagamentos_liquidacoes")
    ]

    # 2. Endpoints Anuais (não aceitam mês)
    endpoints_anuais = [
        ("Itens de Notas Fiscais", "https://api-dados-abertos.tce.ce.gov.br/sim/itens_notas_fiscais")
    ]

    # Prepara tarefas mensais
    for mes in range(1, 13):
        data_ref = int(f"{ano}{str(mes).zfill(2)}")
        for nome, url in endpoints_mensais:
            for m in municipios:
                caminho = os.path.join('data', f"{nome.replace(' ', '_').lower()}_{ano}_{mes:02d}_{m['codigo_municipio']}.parquet")
                lista_de_tarefas.append({
                    'dataset_nome': nome, 'url': url,
                    'params': {"exercicio_orcamento": exercicio, "data_referencia_doc": data_ref, "$format": "json", "codigo_municipio": m['codigo_municipio']},
                    'caminho_arquivo': caminho, 'municipio_nome': m['nome_municipio']
                })

    # Prepara tarefas anuais
    for nome, url in endpoints_anuais:
        for m in municipios:
            caminho = os.path.join('data', f"{nome.replace(' ', '_').lower()}_{ano}_{m['codigo_municipio']}.parquet")
            lista_de_tarefas.append({
                'dataset_nome': nome, 'url': url,
                'params': {"exercicio_orcamento": exercicio, "$format": "json", "codigo_municipio": m['codigo_municipio']},
                'caminho_arquivo': caminho, 'municipio_nome': m['nome_municipio']
            })

    print(f"Total de tarefas a processar: {len(lista_de_tarefas)}")
    
    # Execução Paralela com Barra de Progresso
    max_workers = 5 #
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(tqdm(executor.map(processar_lote, lista_de_tarefas), total=len(lista_de_tarefas), desc="Baixando dados"))

if __name__ == "__main__":
    # Valores padrão de segurança
    ano_inicio = 2025
    ano_fim = 2025

    # Se o usuário passou apenas 1 argumento (ex: python main.py 2024)
    if len(sys.argv) == 2:
        ano_inicio = int(sys.argv[1])
        ano_fim = ano_inicio
        
    # Se o usuário passou 2 argumentos (ex: python main.py 2020 2024)
    elif len(sys.argv) >= 3:
        # Usamos min e max para garantir que o menor ano seja sempre o início
        ano_inicio = min(int(sys.argv[1]), int(sys.argv[2]))
        ano_fim = max(int(sys.argv[1]), int(sys.argv[2]))

    print(f"Iniciando extração paralela para o período de {ano_inicio} a {ano_fim}...")

    # Loop que passa por cada ano do intervalo
    for ano_atual in range(ano_inicio, ano_fim + 1):
        print(f"\n[{ano_atual}] - Iniciando processamento do ano...")
        executar_pipeline(ano_atual)
        print(f"[{ano_atual}] - Processamento concluído!")

    print("\nProcesso total finalizado com sucesso!")