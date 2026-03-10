import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
        .st-emotion-cache-12w0qpk {{ background-color: {escolha['card']} !important; border: 1px solid {escolha['accent']}33 !important; }}
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
    # Tabela original de tarefas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id SERIAL PRIMARY KEY, cliente TEXT, descricao TEXT, 
            data_entrega DATE, responsavel TEXT, status TEXT, motivo TEXT
        )
    ''')
    # Novas tabelas para Equipe e Recados/Anotações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipe (
            id SERIAL PRIMARY KEY, nome TEXT UNIQUE, email TEXT, frequencia_dias INTEGER
        )
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS recados (id SERIAL PRIMARY KEY, destinatario TEXT, mensagem TEXT, concluido BOOLEAN DEFAULT FALSE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS anotacoes (id SERIAL PRIMARY KEY, texto TEXT, data_criacao TEXT)')
    conn.commit()
    conn.close()

criar_tabelas()

# ------------------------------------------------
# 4. FUNÇÃO DE ENVIO DE E-MAIL
# ------------------------------------------------
def enviar_email(destinatario, assunto, corpo):
    try:
        remetente = st.secrets["EMAIL_USER"]
        senha = st.secrets["EMAIL_PASS"]
        
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'html'))
        
        # Configuração para Gmail (Mude se for Outlook/Office365: smtp.office365.com, porta 587)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail para {destinatario}: {e}")
        return False

# ------------------------------------------------
# 5. INTERFACE PRINCIPAL
# ------------------------------------------------
st.title("📋 Meu Workspace Pessoal")

aba1, aba2, aba3, aba4, aba5 = st.tabs(["📌 Tarefas", "👥 Equipe", "🗣️ Recados", "📝 Anotações", "📊 Dashboard"])

# ==========================================
# ABA 2: EQUIPE (Coloquei antes para carregar os responsáveis)
# ==========================================
with aba2:
    st.subheader("👥 Gestão da Equipe")
    
    with st.form("form_equipe", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        novo_nome = c1.text_input("Nome do Integrante")
        novo_email = c2.text_input("E-mail corporativo")
        nova_freq = c3.number_input("Avisar a cada (dias)", min_value=1, value=3)
        
        if st.form_submit_button("Cadastrar Membro"):
            if novo_nome and novo_email:
                try:
                    conn = conectar_banco()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO equipe (nome, email, frequencia_dias) VALUES (%s, %s, %s)", 
                                   (novo_nome, novo_email, nova_freq))
                    conn.commit()
                    conn.close()
                    st.success(f"{novo_nome} adicionado à equipe!")
                    st.rerun()
                except Exception as e:
                    st.error("Erro: Este nome já pode estar cadastrado.")

    st.divider()
    st.markdown("### 📋 Membros Cadastrados")
    conn = conectar_banco()
    df_equipe = pd.read_sql_query("SELECT * FROM equipe ORDER BY id", conn)
    conn.close()
    
    if not df_equipe.empty:
        df_equipe_edit = st.data_editor(df_equipe, hide_index=True, use_container_width=True, key="ed_equipe", disabled=["id"])
        if st.button("💾 Salvar Alterações na Equipe", type="primary"):
            conn = conectar_banco()
            cursor = conn.cursor()
            for index, row in df_equipe_edit.iterrows():
                cursor.execute("UPDATE equipe SET nome = %s, email = %s, frequencia_dias = %s WHERE id = %s", 
                               (row['nome'], row['email'], row['frequencia_dias'], row['id']))
            conn.commit()
            conn.close()
            st.success("Equipe atualizada!")
            st.rerun()
    else:
        st.info("Nenhum membro cadastrado. Adicione pessoas para atribuir tarefas.")

    st.divider()
    st.markdown("### 🚀 Disparo de Notificações")
    st.info("Clique no botão abaixo para analisar todas as tarefas abertas e enviar e-mails aos responsáveis de acordo com as regras de prazo.")
    if st.button("📧 Disparar Lembretes Agora", type="primary"):
        with st.spinner("Processando e-mails..."):
            conn = conectar_banco()
            # Puxa tarefas abertas unindo com os dados do responsável
            query = """
                SELECT t.id, t.descricao, t.data_entrega, t.status, e.nome, e.email, e.frequencia_dias 
                FROM tarefas t
                JOIN equipe e ON t.responsavel = e.nome
                WHERE t.status != 'Concluído'
            """
            df_tarefas_abertas = pd.read_sql_query(query, conn)
            conn.close()
            
            emails_enviados = 0
            hoje = date.today()
            
            for _, row in df_tarefas_abertas.iterrows():
                data_entrega = pd.to_datetime(row['data_entrega']).date()
                dias_restantes = (data_entrega - hoje).days
                
                # Regra: Só avisa se o número de dias restantes for múltiplo da frequência, ou se estiver atrasado (dias < 0)
                if dias_restantes < 0 or dias_restantes % row['frequencia_dias'] == 0:
                    assunto = f"🚨 Lembrete de Tarefa: {row['descricao']}"
                    if dias_restantes < 0:
                        status_texto = f"<strong style='color:red;'>ATRASADA em {abs(dias_restantes)} dias!</strong>"
                    elif dias_restantes == 0:
                        status_texto = "<strong>vence HOJE!</strong>"
                    else:
                        status_texto = f"faltam <strong>{dias_restantes} dias</strong> para a entrega."
                        
                    corpo_html = f"""
                    <h3>Olá, {row['nome']}!</h3>
                    <p>Este é um aviso automático do seu Workspace.</p>
                    <p>A tarefa <strong>{row['descricao']}</strong> {status_texto}</p>
                    <p>Data de Entrega estipulada: {data_entrega.strftime('%d/%m/%Y')}</p>
                    <p>Por favor, atualize o status assim que possível.</p>
                    """
                    
                    if enviar_email(row['email'], assunto, corpo_html):
                        emails_enviados += 1
                        
            st.success(f"Processo finalizado! {emails_enviados} e-mail(s) de lembrete enviado(s).")


# ==========================================
# ABA 1: TAREFAS
# ==========================================
with aba1:
    lista_responsaveis = df_equipe['nome'].tolist() if not df_equipe.empty else ["Sem equipe cadastrada"]
    
    st.subheader("Adicionar Nova Tarefa")
    with st.expander("➕ Criar nova tarefa", expanded=False):
        c1, c2, c3 = st.columns(3)
        cliente_novo = c1.text_input("Cliente")
        desc_nova = c2.text_input("Descrição da Tarefa")
        status_novo = c3.selectbox("Status", ["Não Iniciado", "Iniciado", "Bloqueado", "Concluído"])
        
        c4, c5, c6 = st.columns(3)
        # O responsável agora é um dropdown puxando da equipe
        resp_novo = c4.selectbox("Responsável", lista_responsaveis)
        data_nova = c5.date_input("Data de Entrega", date.today(), format="DD/MM/YYYY")
        
        motivo_novo = ""
        if status_novo == "Bloqueado":
            motivo_novo = c6.text_input("Motivo do Bloqueio")

        if st.button("Salvar Tarefa", type="primary", disabled=(len(lista_responsaveis) == 0 or lista_responsaveis[0] == "Sem equipe cadastrada")):
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
    st.subheader("📋 Gerenciar Tarefas")
    
    conn = conectar_banco()
    df_tarefas = pd.read_sql_query("SELECT * FROM tarefas ORDER BY id DESC", conn)
    conn.close()

    if not df_tarefas.empty:
        df_editado = st.data_editor(
            df_tarefas,
            use_container_width=True,
            hide_index=True,
            key="editor_tarefas",
            disabled=["id"],
            column_config={
                "data_entrega": st.column_config.DateColumn("Data de Entrega", format="DD/MM/YYYY"),
                "status": st.column_config.SelectboxColumn("Status", options=["Não Iniciado", "Iniciado", "Bloqueado", "Concluído"]),
                "responsavel": st.column_config.SelectboxColumn("👤 Responsável", options=lista_responsaveis), # Dropdown também na edição!
            }
        )

        if st.button("💾 Salvar Alterações na Tabela", type="primary"):
            try:
                conn = conectar_banco()
                cursor = conn.cursor()
                for index, row in df_editado.iterrows():
                    cursor.execute("""
                        UPDATE tarefas SET cliente = %s, descricao = %s, data_entrega = %s, 
                            responsavel = %s, status = %s, motivo = %s WHERE id = %s
                    """, (row['cliente'], row['descricao'], row['data_entrega'], row['responsavel'], row['status'], row['motivo'], row['id']))
                conn.commit()
                conn.close()
                st.success("Alterações salvas com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
    else:
        st.write("Nenhuma tarefa encontrada.")

# ==========================================
# ABA 3 e 4 mantidas exatamente iguais ao original...
# (Aba de Recados e Anotações ficam aqui sem alterações visuais profundas)
# ==========================================
with aba3:
    st.write("*(Módulo de recados mantido intacto)*")
    # ... Omitido aqui por brevidade, mas você mantém seu código original da aba Recados

with aba4:
    st.write("*(Módulo de anotações mantido intacto)*")
    # ... Mantém seu código original da aba Anotações

with aba5:
    conn = conectar_banco()
    df_d = pd.read_sql_query("SELECT * FROM tarefas", conn)
    conn.close()
    if not df_d.empty:
        hoje = date.today()
        df_d['data_entrega'] = pd.to_datetime(df_d['data_entrega']).dt.date
        df_d['prazo'] = df_d.apply(lambda r: 'Atrasada' if r['data_entrega'] < hoje and r['status'] != 'Concluído' else 'No Prazo', axis=1)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("🚨 Atrasadas", len(df_d[df_d['prazo'] == 'Atrasada']))
        c2.metric("⏳ Não Iniciadas", len(df_d[df_d['status'] == 'Não Iniciado']))
        c3.metric("✅ Concluídas", len(df_d[df_d['status'] == 'Concluído']))
        
        fig = px.pie(df_d, names='status', hole=0.4, title="Status Geral", color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)