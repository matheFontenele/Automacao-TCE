import time
import requests
import pandas as pd
import json

# --- CONFIGURAÇÕES GERAIS ---
ANO_BASE = 2025

# Carrega a lista de municípios
with open('municipios.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    
# Acessa a lista correta dentro da chave 'elements'
municipios = data['elements']

# Função principal
def extrair_dados(nome_dataset, url_base, params_base, nome_arquivo):
    print(f"\n--- Iniciando extração: {nome_dataset} ---")
    todos_os_dados = []
    
    for m in municipios:
        print(f"[{nome_dataset}] Buscando: {m['nome_municipio']} ({m['codigo_municipio']})")
        
        params = params_base.copy()
        params["codigo_municipio"] = m['codigo_municipio']
        
        try:
            response = requests.get(url_base, headers={"Accept": "application/json"}, params=params)
            
            if response.status_code == 200:
                dados = response.json().get("elements", [])
                if dados:
                    for item in dados:
                        # Adiciona o nome do município para referência
                        item['municipio_referencia'] = m['nome_municipio']
                    todos_os_dados.extend(dados)
                    print(f" -> {len(dados)} registros.")
                else:
                    print(" -> Sem registros.")
            else:
                print(f" -> Erro {response.status_code}")
        except Exception as e:
            print(f" -> Erro de conexão: {e}")
            
        time.sleep(0.3)

    if todos_os_dados:
        # 1. Salva em CSV
        df = pd.DataFrame(todos_os_dados)
        df.to_csv(f"{nome_arquivo}.csv", index=False, encoding='utf-8-sig')
        print(f"Arquivo '{nome_arquivo}.csv' salvo com sucesso!")

        # 2. Salva em JSON
        with open(f"{nome_arquivo}.json", 'w', encoding='utf-8') as f_json:
            json.dump(todos_os_dados, f_json, ensure_ascii=False, indent=4)
        print(f"Arquivo '{nome_arquivo}.json' salvo com sucesso!")
    else:
        print(f"Nenhum dado encontrado para {nome_dataset}.")

# --- EXECUÇÃO DAS EXTRAÇÕES ---

# Loop que vai de 1 até 12
for mes in range(1, 13):
    DATA_REF = int(f"{ANO_BASE}{str(mes).zfill(2)}")
    
    print(f"\n==================================================")
    print(f"   INICIANDO EXTRAÇÃO DO MÊS {mes:02d}/{ANO_BASE}")
    print(f"==================================================")

    # 1. Notas de Empenho
    extrair_dados(
        "Notas de Empenho",
        "https://api-dados-abertos.tce.ce.gov.br/sim/notas_empenhos",
        {"exercicio_orcamento": ANO_BASE, "data_referencia_doc": DATA_REF, "$format": "json"},
        f"notas_empenho_{ANO_BASE}_{mes:02d}"
    )

    # 2. Notas Fiscais
    extrair_dados(
        "Notas Fiscais",
        "https://api-dados-abertos.tce.ce.gov.br/sim/notas_fiscais",
        {"exercicio_orcamento": ANO_BASE, "data_referencia_doc": DATA_REF, "$format": "json"},
        f"notas_fiscais_{ANO_BASE}_{mes:02d}"
    )

# 3. Itens de Notas Fiscais 
print(f"\n==================================================")
print(f"   INICIANDO EXTRAÇÃO ANUAL: ITENS DE NOTAS FISCAIS")
print(f"==================================================")
extrair_dados(
    "Itens de Notas Fiscais",
    "https://api-dados-abertos.tce.ce.gov.br/sim/itens_notas_fiscais",
    {"exercicio_orcamento": ANO_BASE, "$format": "json"},
    f"itens_notas_fiscais_{ANO_BASE}"
)

print("\nProcesso finalizado com sucesso!")