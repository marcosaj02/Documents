import pandas as pd
import os
from datetime import datetime

# Caminho do arquivo de dados
DB_FILE = "data/tarefas_db.xlsx"

def carregar_dados():
    """Carrega as tarefas do Excel ou cria um novo se não existir"""
    if not os.path.exists(DB_FILE):
        # Cria um DataFrame vazio com as colunas certas
        df = pd.DataFrame(columns=["ID", "Tarefa", "Status", "Prioridade", "Data_Criacao"])
        # Salva na pasta data (garante que a pasta existe)
        os.makedirs("data", exist_ok=True)
        df.to_excel(DB_FILE, index=False)
        return df
    
    return pd.read_excel(DB_FILE)

def salvar_tarefa(tarefa, prioridade):
    """Adiciona uma nova tarefa ao Excel"""
    df = carregar_dados()
    
    nova_linha = {
        "ID": len(df) + 1,
        "Tarefa": tarefa,
        "Status": "Pendente",
        "Prioridade": prioridade,
        "Data_Criacao": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    
    # Concatena a nova linha (método moderno do Pandas)
    novo_df = pd.DataFrame([nova_linha])
    df = pd.concat([df, novo_df], ignore_index=True)
    
    df.to_excel(DB_FILE, index=False)