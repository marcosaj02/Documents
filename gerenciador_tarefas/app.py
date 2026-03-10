import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Meu Workspace", page_icon="📋", layout="wide")

# --- 2. CONFIGURAÇÃO DE TEMAS DINÂMICOS ---
with st.sidebar:
    st.markdown("### 🎨 Visual")
    tema = st.selectbox(
        "Selecione o tom do Workspace:",
        ["Dark Modern", "Light Professional", "Steel Blue", "Deep Black"]
    )

config_temas = {
    "Dark Modern": {"bg": "#0E1117", "texto": "#FAFAFA", "card": "#262730", "accent": "#FF4B4B"},
    "Light Professional": {"bg": "#F0F2F6", "texto": "#31333F", "card": "#FFFFFF", "accent": "#007BFF"},
    "Steel Blue": {"bg": "#1A232E", "texto": "#E0E0E0", "card": "#2D3748", "accent": "#6EB5FF"},
    "Deep Black": {"bg": "#000000", "texto": "#D4AF37", "card": "#1A1A1A", "accent": "#D4AF37"}
}

escolha = config_temas[tema]

st.markdown(f"""
    <style>
        .stApp {{ background-color: {escolha['bg']}; color: {escolha['texto']}; }}
        [data-testid="stHeader"] {{ background-color: rgba(0,0,0,0); }}
        .st-emotion-cache-12w0qpk {{
            background-color: {escolha['card']} !important;
            border: 1px solid {escolha['accent']}33 !important;
        }}
        .stMarkdown, p, label {{ color: {escolha['texto']} !important; }}
    </style>
    """, unsafe_allow_html=True)

# ------------------------------------------------
# 3. BANCO DE DADOS
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
# 4. INTERFACE PRINCIPAL
# ------------------------------------------------
st.title("📋 Meu Workspace Pessoal")

aba1, aba2, aba3, aba4 = st.tabs(["📌 Tarefas", "🗣️ Recados", "📝 Anotações", "📊 Dashboard"])

# ==========================================
# ABA 1: TAREFAS
# ==========================================
with aba1:
    st.subheader("Adicionar Nova Tarefa")
    
    with st.expander("➕ Criar nova tarefa", expanded=False):
        c1, c2, c3 = st.columns(3)
        cliente_novo = c1.text_input("Cliente")
        desc_nova = c2.text_input("Descrição da Tarefa")
        status_novo = c3.selectbox("Status", ["Não Iniciado", "Iniciado", "Bloqueado", "Concluído"])
        
        c4, c5, c6 = st.columns(3)
        resp_novo = c4.text_input("Responsável")
        data_nova = c5.date_input("Data de Entrega", date.today(), format="DD/MM/YYYY")
        
        motivo_novo = ""
        if status_novo == "Bloqueado":
            motivo_novo = c6.text_input("Motivo do Bloqueio")

        if st.button("Salvar Tarefa", type="primary"):
            if cliente_novo and desc_nova:
                conn = conectar_banco()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tarefas (cliente, descricao, data_entrega, responsavel, status, motivo) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (cliente_novo, desc_nova, data_nova, resp_novo, status_novo, motivo_novo))
                conn.commit()
                conn.close()
                st.success("Tarefa salva!")
                st.rerun()

    st.divider()

    # --- LISTAGEM E EDIÇÃO DINÂMICA (O LÁPIS/EDITOR) ---
    st.subheader("📋 Gerenciar Tarefas")
    st.info("💡 Você pode editar o Responsável, Data e Status diretamente na tabela abaixo e clicar em 'Salvar Alterações'.")

    conn = conectar_banco()
    df_tarefas = pd.read_sql_query("SELECT * FROM tarefas ORDER BY id DESC", conn)
    conn.close()

    if not df_tarefas.empty:
        # Configuração do editor de dados
        df_editado = st.data_editor(
            df_tarefas,
            use_container_width=True,
            hide_index=True,
            key="editor_tarefas",
            disabled=["id"], # Não permite editar o ID
            column_config={
                "data_entrega": st.column_config.DateColumn("Data de Entrega", format="DD/MM/YYYY"),
                "status": st.column_config.SelectboxColumn("Status", options=["Não Iniciado", "Iniciado", "Bloqueado", "Concluído"]),
                "cliente": st.column_config.TextColumn("Cliente"),
                "responsavel": st.column_config.TextColumn("👤 Responsável"),
            }
        )

        # Verificar se houve mudanças
        if st.button("💾 Salvar Alterações na Tabela", type="primary"):
            try:
                conn = conectar_banco()
                cursor = conn.cursor()
                
                # O Streamlit detecta as linhas que mudaram através do state
                for index, row in df_editado.iterrows():
                    cursor.execute("""
                        UPDATE tarefas 
                        SET cliente = %s, descricao = %s, data_entrega = %s, 
                            responsavel = %s, status = %s, motivo = %s
                        WHERE id = %s
                    """, (row['cliente'], row['descricao'], row['data_entrega'], 
                          row['responsavel'], row['status'], row['motivo'], row['id']))
                
                conn.commit()
                conn.close()
                st.success("Todas as alterações foram salvas com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
    else:
        st.write("Nenhuma tarefa encontrada.")

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
        # Conversão segura para data
        df_d['data_entrega'] = pd.to_datetime(df_d['data_entrega']).dt.date
        df_d['prazo'] = df_d.apply(lambda r: 'Atrasada' if r['data_entrega'] < hoje and r['status'] != 'Concluído' else 'No Prazo', axis=1)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("🚨 Atrasadas", len(df_d[df_d['prazo'] == 'Atrasada']))
        c2.metric("⏳ Não Iniciadas", len(df_d[df_d['status'] == 'Não Iniciado']))
        c3.metric("✅ Concluídas", len(df_d[df_d['status'] == 'Concluído']))
        
        fig = px.pie(df_d, names='status', hole=0.4, title="Status Geral", color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)