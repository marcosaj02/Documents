import sqlite3
import pandas as pd
import hashlib
from datetime import datetime, date

DB_PATH = "data/financeiro.db"

def conectar():
    return sqlite3.connect(DB_PATH)

def hash_senha(senha):
    """Criptografa a senha para segurança básica"""
    return hashlib.sha256(str(senha).encode()).hexdigest()

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    
    # 1. Tabela de Usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    email TEXT UNIQUE,
                    senha TEXT,
                    nome TEXT)''')

    # 2. Categorias
    c.execute('''CREATE TABLE IF NOT EXISTS categorias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT,
                    tipo TEXT,
                    user_id INTEGER)''') 

    # 3. Recorrências
    c.execute('''CREATE TABLE IF NOT EXISTS recorrencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT,
                    valor REAL,
                    dia_vencimento INTEGER,
                    categoria TEXT,
                    tipo TEXT,
                    ativo INTEGER DEFAULT 1,
                    data_limite DATE,
                    user_id INTEGER)''')

    # 4. Transações
    c.execute('''CREATE TABLE IF NOT EXISTS transacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data DATE,
                    nome TEXT,
                    valor REAL,
                    categoria TEXT,
                    tipo TEXT,
                    status TEXT,
                    origem_recorrencia_id INTEGER,
                    user_id INTEGER)''')
    
    conn.commit()
    conn.close()

# --- FUNÇÕES DE USUÁRIO (LOGIN & RECUPERAÇÃO) ---
def criar_usuario(username, email, senha, nome):
    conn = conectar()
    try:
        conn.execute("INSERT INTO usuarios (username, email, senha, nome) VALUES (?, ?, ?, ?)", 
                     (username, email, hash_senha(senha), nome))
        conn.commit()
        return "Sucesso"
    except sqlite3.IntegrityError as e:
        erro = str(e)
        if "username" in erro:
            return "Erro: Este usuário já existe."
        elif "email" in erro:
            return "Erro: Este e-mail já está cadastrado."
        return "Erro desconhecido ao criar usuário."
    finally:
        conn.close()

def verificar_login(username, senha):
    conn = conectar()
    res = conn.execute("SELECT id, nome FROM usuarios WHERE (username = ? OR email = ?) AND senha = ?", 
                       (username, username, hash_senha(senha))).fetchone()
    conn.close()
    return res

def recuperar_senha(email):
    conn = conectar()
    res = conn.execute("SELECT username FROM usuarios WHERE email = ?", (email,)).fetchone()
    conn.close()
    if res:
        return True, res[0]
    return False, None

# --- FUNÇÕES FINANCEIRAS ---
def processar_recorrencias(user_id):
    conn = conectar()
    c = conn.cursor()
    hoje = date.today()
    mes_atual = hoje.strftime("%Y-%m")
    
    recorrencias = c.execute("SELECT * FROM recorrencias WHERE user_id = ? AND ativo = 1", (user_id,)).fetchall()
    
    for rec in recorrencias:
        rec_id, nome, valor, dia, cat, tipo, ativo, data_limite, uid = rec
        
        if data_limite:
            data_lim_obj = datetime.strptime(str(data_limite)[:10], "%Y-%m-%d").date()
            primeiro_dia_mes_atual = date(hoje.year, hoje.month, 1)
            if primeiro_dia_mes_atual > data_lim_obj:
                continue

        try:
            data_vencimento = f"{mes_atual}-{int(dia):02d}"
        except:
            from calendar import monthrange
            ultimo = monthrange(hoje.year, hoje.month)[1]
            data_vencimento = f"{mes_atual}-{ultimo:02d}"
        
        ja_existe = c.execute("""
            SELECT count(*) FROM transacoes 
            WHERE origem_recorrencia_id = ? AND strftime('%Y-%m', data) = ? AND user_id = ?
        """, (rec_id, mes_atual, user_id)).fetchone()[0]
        
        if ja_existe == 0:
            c.execute("""
                INSERT INTO transacoes (data, nome, valor, categoria, tipo, status, origem_recorrencia_id, user_id)
                VALUES (?, ?, ?, ?, ?, 'Pendente', ?, ?)
            """, (data_vencimento, nome, valor, cat, tipo, rec_id, user_id))
            
    conn.commit()
    conn.close()

def ler_transacoes(user_id):
    conn = conectar()
    df = pd.read_sql("SELECT * FROM transacoes WHERE user_id = ? ORDER BY data DESC", conn, params=(user_id,))
    conn.close()
    return df

def adicionar_transacao(user_id, data, nome, valor, categoria, tipo, status):
    conn = conectar()
    conn.execute("INSERT INTO transacoes (data, nome, valor, categoria, tipo, status, user_id) VALUES (?,?,?,?,?,?,?)",
                 (data, nome, valor, categoria, tipo, status, user_id))
    conn.commit()
    conn.close()

def ler_recorrencias(user_id):
    conn = conectar()
    df = pd.read_sql("SELECT * FROM recorrencias WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def atualizar_recorrencias(user_id, df_novo):
    conn = conectar()
    c = conn.cursor()
    
    if 'id' in df_novo.columns:
        ids_mantidos = df_novo['id'].dropna().astype(int).tolist()
        if ids_mantidos:
            marcadores = ','.join('?' * len(ids_mantidos))
            c.execute(f"DELETE FROM recorrencias WHERE user_id = ? AND id NOT IN ({marcadores})", [user_id] + ids_mantidos)
        else:
            c.execute("DELETE FROM recorrencias WHERE user_id = ?", (user_id,))

    registros = df_novo.to_dict('records')
    for row in registros:
        ativo_int = 1 if row.get('ativo') == True else 0
        data_lim = row.get('data_limite')
        if pd.isna(data_lim): 
            data_lim = None
        else:
            data_lim = str(data_lim)[:10]
            
        if pd.isna(row.get('id')):
             c.execute("""
                INSERT INTO recorrencias (nome, valor, dia_vencimento, categoria, tipo, ativo, data_limite, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (row['nome'], row['valor'], row['dia_vencimento'], row['categoria'], row['tipo'], ativo_int, data_lim, user_id))
        else:
             c.execute("""
                UPDATE recorrencias 
                SET nome = ?, valor = ?, dia_vencimento = ?, categoria = ?, tipo = ?, ativo = ?, data_limite = ?
                WHERE id = ? AND user_id = ?
            """, (row['nome'], row['valor'], row['dia_vencimento'], row['categoria'], row['tipo'], 
                  ativo_int, data_lim, row['id'], user_id))
    conn.commit()
    conn.close()

def confirmar_transacao(transacao_id, data_real):
    conn = conectar()
    conn.execute("UPDATE transacoes SET status = 'Pago', data = ? WHERE id = ?", (data_real, transacao_id))
    conn.commit()
    conn.close()

# --- NOVA FUNÇÃO: ATUALIZAR/EXCLUIR TRANSAÇÕES MANUAIS ---
def atualizar_transacoes(user_id, df_novo):
    conn = conectar()
    c = conn.cursor()
    
    # 1. DELETAR AS LINHAS QUE FORAM EXCLUÍDAS NA TELA
    if 'id' in df_novo.columns:
        ids_mantidos = df_novo['id'].dropna().astype(int).tolist()
        if ids_mantidos:
            marcadores = ','.join('?' * len(ids_mantidos))
            c.execute(f"DELETE FROM transacoes WHERE user_id = ? AND id NOT IN ({marcadores})", [user_id] + ids_mantidos)
        else:
            c.execute("DELETE FROM transacoes WHERE user_id = ?", (user_id,))

    # 2. INSERIR NOVAS E ATUALIZAR AS EXISTENTES
    registros = df_novo.to_dict('records')
    
    for row in registros:
        data_val = row.get('data')
        if pd.isna(data_val):
            continue 
        
        # Garante que a data vá para o SQLite no formato correto YYYY-MM-DD
        data_str = str(data_val)[:10] 
        
        if pd.isna(row.get('id')):
             c.execute("""
                INSERT INTO transacoes (data, nome, valor, categoria, tipo, status, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data_str, row['nome'], row['valor'], row['categoria'], row['tipo'], row['status'], user_id))
        else:
             c.execute("""
                UPDATE transacoes 
                SET data = ?, nome = ?, valor = ?, categoria = ?, tipo = ?, status = ?
                WHERE id = ? AND user_id = ?
            """, (data_str, row['nome'], row['valor'], row['categoria'], row['tipo'], row['status'], row['id'], user_id))
                  
    conn.commit()
    conn.close()