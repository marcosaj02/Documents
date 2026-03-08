import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import io
from datetime import date, timedelta
import warnings

# --- 1. SELETOR DE TEMAS EM TEMPO DE EXECUÇÃO ---
# Criamos uma barra lateral discreta para a configuração
with st.sidebar:
    st.write("🎨 **Configurações de Visual**")
    tema_escolhido = st.selectbox(
        "Escolha o Tema:",
        ["Padrão (Dark)", "Light Grey", "Steel Blue", "Black & Gold"]
    )

# Lógica de Cores para cada tema
temas = {
    "Padrão (Dark)": {"bg": "#0E1117", "texto": "#FAFAFA", "card": "#262730"},
    "Light Grey": {"bg": "#F0F2F6", "texto": "#31333F", "card": "#FFFFFF"},
    "Steel Blue": {"bg": "#1A232E", "texto": "#E0E0E0", "card": "#2D3748"},
    "Black & Gold": {"bg": "#000000", "texto": "#D4AF37", "card": "#1A1A1A"}
}

t = temas[tema_escolhido]

# Injeção de CSS para mudar as cores em tempo real
st.markdown(f"""
    <style>
        .stApp {{
            background-color: {t['bg']};
            color: {t['texto']};
        }}
        [data-testid="stHeader"] {{
            background-color: rgba(0,0,0,0);
        }}
        .st-emotion-cache-12w0qpk {{
            background-color: {t['card']};
        }}
    </style>
    """, unsafe_allow_html=True)
warnings.filterwarnings('ignore', category=UserWarning)

# ------------------------------------------------
# 1. CONFIGURAÇÃO DO BANCO DE DADOS
# ------------------------------------------------
def conectar_banco():
    return psycopg2.connect(st.secrets["DB_URL"])

def criar_tabelas():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id SERIAL PRIMARY KEY, cliente TEXT, descricao TEXT, 
            data_entrega DATE, responsavel TEXT, status TEXT, motivo TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recados (
            id SERIAL PRIMARY KEY, destinatario TEXT, mensagem TEXT, concluido BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anotacoes (
            id SERIAL PRIMARY KEY, texto TEXT, data_criacao TEXT
        )
    ''')
    conn.commit()
    conn.close()

criar_tabelas()

# ------------------------------------------------
# 2. INTERFACE
# ------------------------------------------------
st.set_page_config(page_title="Meu Workspace", page_icon="📋", layout="wide")
st.title("📋 Meu Workspace Pessoal")

aba1, aba2, aba3, aba4 = st.tabs(["📌 Tarefas", "🗣️ Recados", "📝 Anotações", "📊 Dashboard"])

# ==========================================
# ABA 1: TAREFAS (Ordem de Tab Horizontal Forçada)
# ==========================================
with aba1:
    st.subheader("Adicionar Nova Tarefa")
    
    # --- LINHA 1 ---
    c1, c2, c3 = st.columns(3)
    # Ao criar os inputs assim, o navegador segue a ordem exata do código
    cliente = c1.text_input("Cliente", key="input_cliente")
    descricao = c2.text_input("Descrição da Tarefa", key="input_desc")
    status = c3.selectbox("Status", ["Não Iniciado", "Iniciado", "Bloqueado", "Concluído"], key="input_status")

    # --- LINHA 2 ---
    c4, c5, c6 = st.columns(3)
    responsavel = c4.text_input("Responsável", key="input_resp")
    data_entrega = c5.date_input("Data de Entrega", date.today(), format="DD/MM/YYYY", key="input_data")
    
    # Motivo aparece na terceira coluna da segunda linha se bloqueado
    motivo = ""
    if status == "Bloqueado":
        motivo = c6.text_input("Motivo do Bloqueio", key="input_motivo")
        
# ==========================================
# ABA 2: RECADOS
# ==========================================
with aba2:
    with st.form("form_recado", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        dest = c1.text_input("Para quem?")
        msg = c2.text_input("Mensagem")
        if st.form_submit_button("Adicionar Recado"):
            conn = conectar_banco()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO recados (destinatario, mensagem) VALUES (%s, %s)", (dest, msg))
            conn.commit()
            conn.close()
            st.rerun()

    conn = conectar_banco()
    df_recados = pd.read_sql_query("SELECT * FROM recados WHERE concluido = FALSE", conn)
    conn.close()
    for i, row in df_recados.iterrows():
        col_m, col_b = st.columns([4, 1])
        col_m.warning(f"🗣️ **Para {row['destinatario']}:** {row['mensagem']}")
        if col_b.button("✅ Concluir", key=f"rec_{row['id']}"):
            conn = conectar_banco()
            cursor = conn.cursor()
            cursor.execute("UPDATE recados SET concluido = TRUE WHERE id = %s", (row['id'],))
            conn.commit()
            conn.close()
            st.rerun()
            
# ==========================================
# ABA 3: ANOTAÇÕES
# ==========================================
with aba3:
    with st.form("form_nota", clear_on_submit=True):
        texto = st.text_area("O que deseja anotar?")
        if st.form_submit_button("Salvar Anotação"):
            conn = conectar_banco()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO anotacoes (texto, data_criacao) VALUES (%s, %s)", (texto, date.today().strftime("%d/%m/%Y")))
            conn.commit()
            conn.close()
            st.rerun()

    conn = conectar_banco()
    df_notas = pd.read_sql_query("SELECT * FROM anotacoes ORDER BY id DESC", conn)
    conn.close()
    cols = st.columns(3)
    for i, row in df_notas.iterrows():
        with cols[i % 3]:
            with st.container(border=True):
                st.caption(f"📅 {row['data_criacao']}")
                st.write(row['texto'])
                if st.button("🗑️ Excluir", key=f"not_{row['id']}"):
                    conn = conectar_banco()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM anotacoes WHERE id = %s", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

# ==========================================
# ABA 4: DASHBOARD
# ==========================================
with aba4:
    conn = conectar_banco()
    df_d = pd.read_sql_query("SELECT * FROM tarefas", conn)
    conn.close()
    if not df_d.empty:
        hoje = date.today()
        df_d['prazo'] = df_d.apply(lambda r: 'Atrasada' if pd.to_datetime(r['data_entrega']).date() < hoje and r['status'] != 'Concluído' else 'No Prazo', axis=1)
        c1, c2, c3 = st.columns(3)
        c1.metric("🚨 Atrasadas", len(df_d[df_d['prazo'] == 'Atrasada']))
        c2.metric("⏳ Não Iniciadas", len(df_d[df_d['status'] == 'Não Iniciado']))
        c3.metric("✅ Concluídas", len(df_d[df_d['status'] == 'Concluído']))
        
        fig = px.pie(df_d, names='status', hole=0.4, title="Status Geral")
        st.plotly_chart(fig, use_container_width=True)