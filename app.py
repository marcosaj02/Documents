import streamlit as st
import pandas as pd
from datetime import date, timedelta
from modules.database import *

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Gestor Financeiro Pro", layout="wide", page_icon="💳")
inicializar_db()

# --- SISTEMA DE LOGIN (V3 - Com Email e Recuperação) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['user_nome'] = None

def tela_login():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Acesso Seguro")
        
        # Agora temos 3 abas
        tab1, tab2, tab3 = st.tabs(["Login", "Criar Conta", "Esqueci a Senha"])
        
        # --- ABA 1: LOGIN ---
        with tab1:
            with st.form("login_form"):
                usuario = st.text_input("Usuário ou E-mail")
                senha = st.text_input("Senha", type="password")
                submit_login = st.form_submit_button("Entrar", type="primary")
                
                if submit_login:
                    user_data = verificar_login(usuario, senha)
                    if user_data:
                        st.session_state['logged_in'] = True
                        st.session_state['user_id'] = user_data[0]
                        st.session_state['user_nome'] = user_data[1]
                        st.rerun()
                    else:
                        st.error("❌ Usuário/E-mail ou senha incorretos.")
        
        # --- ABA 2: CADASTRO COMPLETO ---
        with tab2:
            st.write("Crie sua conta para começar.")
            with st.form("cadastro_form", clear_on_submit=True):
                novo_user = st.text_input("Usuário (Login)")
                novo_email = st.text_input("E-mail (Para recuperação)")
                
                c_s1, c_s2 = st.columns(2)
                nova_senha = c_s1.text_input("Senha", type="password")
                confirma_senha = c_s2.text_input("Repita a Senha", type="password")
                
                novo_nome = st.text_input("Seu Nome")
                
                submit_cadastro = st.form_submit_button("Cadastrar")
                
                if submit_cadastro:
                    if not novo_user or not novo_email or not nova_senha:
                        st.warning("⚠️ Preencha todos os campos obrigatórios.")
                    elif nova_senha != confirma_senha:
                        st.error("❌ As senhas não coincidem!")
                    else:
                        # Chama a função que trata duplicidade
                        resultado = criar_usuario(novo_user, novo_email, nova_senha, novo_nome)
                        
                        if resultado == "Sucesso":
                            st.success("✅ Conta criada com sucesso! Acesse a aba de Login.")
                        else:
                            st.error(f"❌ {resultado}")

        # --- ABA 3: RECUPERAÇÃO DE SENHA ---
        with tab3:
            st.write("Informe seu e-mail para recuperar o acesso.")
            with st.form("recupera_form"):
                email_rec = st.text_input("Seu E-mail cadastrado")
                submit_rec = st.form_submit_button("Recuperar Senha")
                
                if submit_rec:
                    existe, username_rec = recuperar_senha(email_rec)
                    if existe:
                        # Simulando envio de email (Em produção, aqui usariamos biblioteca SMTP)
                        st.success(f"✅ Um link de redefinição foi enviado para: {email_rec}")
                        st.info(f"(Simulação: Seu usuário é '{username_rec}'. Entre em contato com o suporte para resetar a senha no banco.)")
                    else:
                        st.error("❌ E-mail não encontrado no sistema.")

# --- SE NÃO TIVER LOGADO, MOSTRA LOGIN E PARA AQUI ---
if not st.session_state['logged_in']:
    tela_login()
    st.stop()

# =========================================================
# A PARTIR DAQUI SÓ RODA SE O USUÁRIO ESTIVER LOGADO
# =========================================================

USER_ID = st.session_state['user_id']
processar_recorrencias(USER_ID)

with st.sidebar:
    st.write(f"Olá, **{st.session_state['user_nome']}** 👋")
    if st.button("Sair"):
        st.session_state['logged_in'] = False
        st.rerun()
    st.divider()
    menu = st.radio("Menu", ["Dashboard", "Lançamentos", "Configurar Recorrências"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Visão Geral")
    df = ler_transacoes(USER_ID)
    
    if not df.empty:
        df['data'] = pd.to_datetime(df['data'])
        mes_atual = date.today().strftime("%Y-%m")
        df_mes = df[df['data'].dt.strftime('%Y-%m') == mes_atual]
        
        # Alertas
        hoje = pd.to_datetime(date.today())
        contas_vencendo = df_mes[
            (df_mes['status'] == 'Pendente') & 
            (df_mes['tipo'] == 'Despesa') & 
            (df_mes['data'] <= hoje + timedelta(days=3))
        ]
        
        if not contas_vencendo.empty:
            st.error(f"🚨 {len(contas_vencendo)} contas vencendo!")
            for _, row in contas_vencendo.iterrows():
                st.write(f"📅 {row['data'].strftime('%d/%m')} - {row['nome']} (R$ {row['valor']:.2f})")

        # Métricas
        rec = df_mes[df_mes['tipo'] == 'Receita']['valor'].sum()
        desp = df_mes[df_mes['tipo'] == 'Despesa']['valor'].sum()
        saldo = rec - desp
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Entradas", f"R$ {rec:,.2f}")
        c2.metric("Saídas", f"R$ {desp:,.2f}")
        c3.metric("Saldo", f"R$ {saldo:,.2f}", delta=saldo)
        
        st.divider()
        st.subheader("Extrato")
        st.dataframe(df_mes, use_container_width=True, hide_index=True)
    else:
        st.info("Bem-vindo! Comece lançando seus gastos ou configurando as recorrências.")

# --- LANÇAMENTOS ---
elif menu == "Lançamentos":
    st.subheader("💸 Lançamento Manual")
    with st.form("form_gasto", clear_on_submit=True):
        col1, col2 = st.columns(2)
        data = col1.date_input("Data", date.today())
        nome = col2.text_input("Descrição")
        col3, col4, col5 = st.columns(3)
        valor = col3.number_input("Valor", min_value=0.0, format="%.2f")
        cat = col4.selectbox("Categoria", ["Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", "Outros"])
        tipo = col5.selectbox("Tipo", ["Despesa", "Receita"])
        
        if st.form_submit_button("Salvar Lançamento"):
            adicionar_transacao(USER_ID, data, nome, valor, cat, tipo, "Pago")
            st.success("Lançamento salvo!")
            st.rerun()

# --- RECORRÊNCIAS ---
elif menu == "Configurar Recorrências":
    st.subheader("⚙️ Contas Fixas & Assinaturas")
    st.info("Configure aqui o que se repete todo mês (Ex: Aluguel, Salário, Netflix).")
    
    df_rec = ler_recorrencias(USER_ID)
    
    if not df_rec.empty:
        df_rec["ativo"] = df_rec["ativo"].apply(lambda x: True if x == 1 else False)

    edited_df = st.data_editor(
        df_rec,
        num_rows="dynamic",
        use_container_width=True,
        column_order=["nome", "valor", "dia_vencimento", "categoria", "tipo", "data_limite", "ativo"],
        column_config={
            "nome": st.column_config.TextColumn("Descrição", required=True),
            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.0),
            "dia_vencimento": st.column_config.NumberColumn("Dia Venc.", min_value=1, max_value=31),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=["Despesa", "Receita"], required=True),
            "categoria": st.column_config.SelectboxColumn("Categoria", options=["Moradia", "Transporte", "Alimentação", "Salário", "Lazer", "Saúde"], required=True),
            "data_limite": st.column_config.DateColumn("Válido Até (Opcional)"),
            "ativo": st.column_config.CheckboxColumn("Ativo?", default=True)
        }
    )

    if st.button("💾 Salvar Alterações", type="primary"):
        try:
            atualizar_recorrencias(USER_ID, edited_df)
            st.success("Configurações salvas!")
            processar_recorrencias(USER_ID)
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")
