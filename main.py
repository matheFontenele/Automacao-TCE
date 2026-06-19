import os
import sys
import datetime
import requests
import pandas as pd
import concurrent.futures
import json
from tqdm import tqdm
from src.extraction import processar_lote, gerar_tarefas, executar_pipeline, formatar_log_terminal


# Função principal para execução direta via terminal
if __name__ == "__main__":
    # Valores padrão caso rode sem argumentos
    ano_inicio = 2025
    ano_fim = 2025

    # Lendo argumentos do terminal (ex: python main.py 2024 2026)
    if len(sys.argv) == 2:
        ano_inicio = int(sys.argv[1])
        ano_fim = ano_inicio
    elif len(sys.argv) >= 3:
        ano_inicio = min(int(sys.argv[1]), int(sys.argv[2]))
        ano_fim = max(int(sys.argv[1]), int(sys.argv[2]))

    # Função interna para interceptar e colorir os logs enviados pelas threads
    def log_colorido_terminal(msg):
        msg_formatada = formatar_log_terminal(msg)
        tqdm.write(msg_formatada)

    print(f"\033[36m🚀 Preparando ambiente para extração de dados...\033[0m")

    try:
        # 🔄 Executa o pipeline de forma isolada e limpa para cada ano do intervalo
        for ano in range(ano_inicio, ano_fim + 1):
            print(f"\n\033[34m📅 Processando lote do ano: {ano}\033[0m")
            executar_pipeline(
                ano=ano,
                log_func=log_colorido_terminal  # Passa o interceptador colorido para o pipeline
            )
            
        print("\n\033[32m✅ Processo total finalizado com sucesso!\033[0m")
    except Exception as e:
        print(f"\n\033[31m❌ Erro crítico durante a execução: {e}\033[0m")