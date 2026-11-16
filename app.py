from datetime import datetime, date
import pandas as pd
import streamlit as st
from supabase import create_client

# Configuração da Página
st.set_page_config(
    page_title="Controle FEFO - Laticínios", page_icon="🧀", layout="wide"
)

# --- OCULTAR MARCA D'ÁGUA E ELEMENTOS DO STREAMLIT ---
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none !important;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


supabase = init_connection()

# --- FUNÇÕES DE BANCO DE DADOS ---
def get_produtos():
    response = supabase.table("produtos").select("*").order("nome_produto").execute()
    return response.data


def get_estoque_fefo():
    response = supabase.table("vw_estoque_fefo").select("*").execute()
    return response.data


def get_entradas():
    response = supabase.table("entradas").select("*, produtos(nome_produto)").order("data_entrada", desc=True).execute()
    return response.data


def get_saidas():
    response = supabase.table("saidas").select("*, entradas(numero_lote, produtos(nome_produto))").order("data_saida", desc=True).execute()
    return response.data


def get_usuarios():
    response = supabase.table("usuarios").select("*").order("nome_login").execute()
    return response.data


# --- CONTROLE DE SESSÃO (LOGIN) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario_logado"] = None
    st.session_state["perfil"] = None


# --- TELA DE LOGIN (OBRIGATÓRIA NO TOPO) ---
if not st.session_state["autenticado"]:
    st.title("🧀 Controle FEFO - Acesso ao Sistema")
    st.markdown("Por favor, faça login com suas credenciais para continuar.")

    with st.form("form_login"):
        login_input = st.text_input("Usuário (Login)")
        senha_input = st.text_input("Senha", type="password")
        botao_login = st.form_submit_button("Entrar no Sistema")

        if botao_login:
            if not login_input or not senha_input:
                st.error("Preencha o usuário e a senha.")
            else:
                try:
                    res = supabase.table("usuarios").select("*").eq("nome_login", login_input).eq("senha", senha_input).execute()
                    usuarios_encontrados = res.data
                    if usuarios_encontrados:
                        user = usuarios_encontrados[0]
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_logado"] = user["nome_login"]
                        st.session_state["perfil"] = user["perfil"]
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")
                except Exception as e:
                    st.error(f"Erro ao autenticar: {e}")
    
    st.stop()


# ==========================================
# APLICATIVO PRINCIPAL (APÓS O LOGIN)
# ==========================================

perfil_atual = st.session_state["perfil"]
usuario_atual = st.session_state["usuario_logado"]

# --- BARRA LATERAL (RODAPÉ FIXO PARA PERFIL E LOGOUT) ---
with st.sidebar.container(bottom=True):
    st.markdown(f"👤 **Logado:** {usuario_atual}")
    st.markdown(f"🛡️ **Perfil:** `{perfil_atual}`")
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state["autenticado"] = False
        st.session_state["usuario_logado"] = None
        st.session_state["perfil"] = None
        st.rerun()

# Montar opções de menu visíveis com st.radio
opcoes_menu = [
    "📊 Painel FEFO & Estoque",
    "📥 Entradas (Recebimento & Gestão)",
    "🚚 Saídas (Expedição & Gestão)",
    "📋 Cadastro & Gestão de Produtos",
]

if perfil_atual == "Administrador":
    opcoes_menu.append("👥 Gerenciar Usuários")

st.sidebar.markdown("### Navegação")
menu = st.sidebar.radio("Ir para:", opcoes_menu, label_visibility="collapsed")

st.title("🧀 Controle de Estoque & Expedição FEFO")
st.markdown("Gerenciamento inteligente de laticínios baseado no critério **Primeiro que Vence, Primeiro que Sai (FEFO)**.")


# ==========================================
# 1. PAINEL FEFO & ESTOQUE
# ==========================================
if menu == "📊 Painel FEFO & Estoque":
    st.header("Painel Geral de Validades e Posição de Estoque")

    dados = get_estoque_fefo()

    if not dados:
        st.info("Nenhum lote ativo no estoque no momento.")
    else:
        df = pd.DataFrame(dados)

        total_unidades = df["saldo_atual"].sum()
        total_lotes = len(df)
        lotes_criticos = len(df[df["dias_para_vencer"] <= 7])
        lotes_atencao = len(df[(df["dias_para_vencer"] > 7) & (df["dias_para_vencer"] <= 15)])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📦 Saldo Total (Un)", f"{total_unidades:,.0f}".replace(",", "."))
        col2.metric("📋 Lotes Ativos", total_lotes)
        col3.metric("🚨 Críticos (≤ 7 dias)", lotes_criticos, delta_color="inverse")
        col4.metric("⚠️ Atenção (8-15 dias)", lotes_atencao)

        st.divider()

        status_filter = st.selectbox(
            "Filtrar por Status FEFO",
            ["Todos", "Crítico (<= 7d)", "Atenção (8-15d)", "Seguro (> 15d)"],
        )

        if status_filter != "Todos":
            df_filtered = df[df["status_fefo"] == status_filter]
        else:
            df_filtered = df

        st.subheader("Fila de Expedição FEFO (Prioridade por Vencimento)")
        
        df_display = df_filtered[
            [
                "numero_lote",
                "nome_produto",
                "data_validade",
                "saldo_atual",
                "dias_para_vencer",
                "status_fefo",
                "fornecedor",
                "nota_fiscal",
            ]
        ].copy()

        df_display.columns = [
            "Nº do Lote",
            "Produto",
            "Validade",
            "Saldo Atual",
            "Dias p/ Vencer",
            "Status",
            "Fornecedor",
            "Nota Fiscal",
        ]

        st.dataframe(df_display, use_container_width=True, hide_index=True)


# ==========================================
# 2. ENTRADAS (CADASTRO, EDIÇÃO E EXCLUSÃO)
# ==========================================
elif menu == "📥 Entradas (Recebimento & Gestão)":
    st.header("Gerenciamento de Entradas (Lotes)")

    if perfil_atual == "Administrador":
        abas = st.tabs(["➕ Registrar Nova Entrada", "✏️ Gerenciar Entradas Existentes"])
        aba_cad, aba_ger = abas[0], abas[1]
    else:
        aba_cad = st.container()
        aba_ger = None
        st.info("ℹ️ Perfil Funcionário: Acesso permitido apenas para cadastrar novas entradas.")

    produtos = get_produtos()
    produto_dict = {p["nome_produto"]: p["id"] for p in produtos} if produtos else {}

    with aba_cad:
        if not produto_dict:
            st.warning("Cadastre produtos primeiro na aba de Produtos.")
        else:
            with st.form("form_entrada"):
                col1, col2 = st.columns(2)
                with col1:
                    produto_selecionado = st.selectbox("Produto", list(produto_dict.keys()))
                    numero_lote = st.text_input("Número do Lote do Fabricante")
                    quantidade_recebida = st.number_input("Quantidade Recebida (Un/Caixas)", min_value=1, step=1)
                    data_entrada = st.date_input("Data de Entrada", value=date.today())
                with col2:
                    data_validade = st.date_input("Data de Validade (Crucial para o FEFO)")
                    fornecedor = st.text_input("Fornecedor / Origem")
                    nota_fiscal = st.text_input("Número da Nota Fiscal (NF)")

                submitted = st.form_submit_button("Salvar Entrada de Lote")
                if submitted:
                    if not numero_lote or not fornecedor or not nota_fiscal:
                        st.error("Preencha todos os campos obrigatórios.")
                    else:
                        try:
                            supabase.table("entradas").insert({
                                "data_entrada": str(data_entrada),
                                "numero_lote": numero_lote,
                                "produto_id": produto_dict[produto_selecionado],
                                "quantidade_recebida": int(quantidade_recebida),
                                "data_validade": str(data_validade),
                                "fornecedor": fornecedor,
                                "nota_fiscal": nota_fiscal,
                            }).execute()
                            st.success("Entrada registrada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")

    if aba_ger is not None:
        with aba_ger:
            st.subheader("Editar ou Excluir Entradas")
            entradas_list = get_entradas()
            if not entradas_list:
                st.info("Nenhuma entrada cadastrada.")
            else:
                entrada_opcoes = {f"Lote: {e['numero_lote']} | Produto: {e['produtos']['nome_produto']} | Qtd: {e['quantidade_recebida']} | Val: {e['data_validade']}": e for e in entradas_list}
                escolha_ent = st.selectbox("Selecione a Entrada para Gerenciar", list(entrada_opcoes.keys()))
                ent_selecionada = entrada_opcoes[escolha_ent]

                with st.form("form_edita_entrada"):
                    col1, col2 = st.columns(2)
                    with col1:
                        novo_lote = st.text_input("Número do Lote", value=ent_selecionada["numero_lote"])
                        nova_qtd = st.number_input("Quantidade Recebida", min_value=1, value=int(ent_selecionada["quantidade_recebida"]))
                        nova_data_ent = st.date_input("Data de Entrada", value=datetime.strptime(ent_selecionada["data_entrada"], "%Y-%m-%d").date())
                    with col2:
                        nova_validade = st.date_input("Data de Validade", value=datetime.strptime(ent_selecionada["data_validade"], "%Y-%m-%d").date())
                        novo_forn = st.text_input("Fornecedor", value=ent_selecionada["fornecedor"] or "")
                        nova_nf = st.text_input("Nota Fiscal", value=ent_selecionada["nota_fiscal"] or "")

                    atualizar_ent = st.form_submit_button("💾 Salvar Alterações na Entrada")

                    if atualizar_ent:
                        try:
                            supabase.table("entradas").update({
                                "numero_lote": novo_lote,
                                "quantidade_recebida": int(nova_qtd),
                                "data_entrada": str(nova_data_ent),
                                "data_validade": str(nova_validade),
                                "fornecedor": novo_forn,
                                "nota_fiscal": nova_nf
                            }).eq("id", ent_selecionada["id"]).execute()
                            st.success("Entrada atualizada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")

                st.divider()
                if st.button("🗑️ Excluir esta Entrada", type="secondary"):
                    st.session_state["confirmar_excluir_entrada"] = ent_selecionada["id"]

                if st.session_state.get("confirmar_excluir_entrada") == ent_selecionada["id"]:
                    st.warning("⚠️ **Tem certeza que deseja excluir esta entrada?** (Isso também removerá saídas vinculadas a este lote).")
                    col_sim, col_nao = st.columns(2)
                    if col_sim.button("Sim, Excluir Definitivamente", key="sim_del_ent"):
                        try:
                            supabase.table("entradas").delete().eq("id", ent_selecionada["id"]).execute()
                            st.success("Entrada excluída com sucesso!")
                            del st.session_state["confirmar_excluir_entrada"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
                    if col_nao.button("Cancelar", key="nao_del_ent"):
                        del st.session_state["confirmar_excluir_entrada"]
                        st.rerun()


# ==========================================
# 3. SAÍDAS (EXPEDIÇÃO, EDIÇÃO E EXCLUSÃO)
# ==========================================
elif menu == "🚚 Saídas (Expedição & Gestão)":
    st.header("Expedição de Mercadoria para os Mercados")

    if perfil_atual == "Administrador":
        abas_s = st.tabs(["🚚 Registrar Nova Saída", "✏️ Gerenciar Saídas Existentes"])
        aba_cad_s, aba_ger_s = abas_s[0], abas_s[1]
    else:
        aba_cad_s = st.container()
        aba_ger_s = None
        st.info("ℹ️ Perfil Funcionário: Acesso permitido apenas para registrar novas saídas.")

    estoque = get_estoque_fefo()

    with aba_cad_s:
        if not estoque:
            st.warning("Não há saldo disponível em estoque para expedição.")
        else:
            with st.form("form_saida"):
                col1, col2 = st.columns(2)
                with col1:
                    cliente_mercado = st.text_input("Cliente / Rede de Supermercados")
                    numero_pedido = st.text_input("Número do Pedido / Remessa")
                    data_saida = st.date_input("Data da Saída", value=date.today())
                with col2:
                    lotes_opcoes = {
                        f"Lote: {item['numero_lote']} | {item['nome_produto']} | Val: {item['data_validade']} (Saldo: {item['saldo_atual']} un)": item
                        for item in estoque
                    }
                    lote_escolhido_str = st.selectbox("Selecione o Lote (FEFO)", list(lotes_opcoes.keys()))
                    lote_selecionado = lotes_opcoes[lote_escolhido_str]
                    max_qtd = lote_selecionado["saldo_atual"]

                    quantidade_expedida = st.number_input(
                        f"Quantidade a Expedir (Disponível: {max_qtd})",
                        min_value=1,
                        max_value=int(max_qtd),
                        step=1,
                    )

                submitted_saida = st.form_submit_button("Confirmar Expedição")
                if submitted_saida:
                    if not cliente_mercado or not numero_pedido:
                        st.error("Preencha o mercado e o número do pedido.")
                    else:
                        try:
                            supabase.table("saidas").insert({
                                "data_saida": str(data_saida),
                                "entrada_id": int(lote_selecionado["entrada_id"]),
                                "quantidade_expedida": int(quantidade_expedida),
                                "cliente_mercado": cliente_mercado,
                                "numero_pedido": numero_pedido,
                            }).execute()
                            st.success("Saída expedida com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar saída: {e}")

    if aba_ger_s is not None:
        with aba_ger_s:
            st.subheader("Editar ou Excluir Saídas (Expedições)")
            saidas_list = get_saidas()
            if not saidas_list:
                st.info("Nenhuma saída registrada.")
            else:
                saida_opcoes = {f"Pedido: {s['numero_pedido']} | Mercado: {s['cliente_mercado']} | Qtd: {s['quantidade_expedida']}": s for s in saidas_list}
                escolha_s = st.selectbox("Selecione a Saída para Gerenciar", list(saida_opcoes.keys()))
                saida_selecionada = saida_opcoes[escolha_s]

                with st.form("form_edita_saida"):
                    col1, col2 = st.columns(2)
                    with col1:
                        novo_mercado = st.text_input("Cliente / Mercado", value=saida_selecionada["cliente_mercado"])
                        novo_pedido = st.text_input("Número do Pedido", value=saida_selecionada["numero_pedido"])
                    with col2:
                        nova_qtd_exp = st.number_input("Quantidade Expedida", min_value=1, value=int(saida_selecionada["quantidade_expedida"]))
                        nova_data_said = st.date_input("Data da Saída", value=datetime.strptime(saida_selecionada["data_saida"], "%Y-%m-%d").date())

                    atualizar_said = st.form_submit_button("💾 Salvar Alterações na Saída")

                    if atualizar_said:
                        try:
                            supabase.table("saidas").update({
                                "cliente_mercado": novo_mercado,
                                "numero_pedido": novo_pedido,
                                "quantidade_expedida": int(nova_qtd_exp),
                                "data_saida": str(nova_data_said)
                            }).eq("id", saida_selecionada["id"]).execute()
                            st.success("Saída atualizada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")

                st.divider()
                if st.button("🗑️ Excluir esta Saída", type="secondary"):
                    st.session_state["confirmar_excluir_saida"] = saida_selecionada["id"]

                if st.session_state.get("confirmar_excluir_saida") == saida_selecionada["id"]:
                    st.warning("⚠️ **Tem certeza que deseja excluir esta saída?** (O saldo retornará ao estoque do lote).")
                    col_sim, col_nao = st.columns(2)
                    if col_sim.button("Sim, Excluir Definitivamente", key="sim_del_said"):
                        try:
                            supabase.table("saidas").delete().eq("id", saida_selecionada["id"]).execute()
                            st.success("Saída excluída com sucesso!")
                            del st.session_state["confirmar_excluir_saida"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
                    if col_nao.button("Cancelar", key="nao_del_said"):
                        del st.session_state["confirmar_excluir_saida"]
                        st.rerun()


# ==========================================
# 4. CADASTRO DE PRODUTOS
# ==========================================
elif menu == "📋 Cadastro & Gestão de Produtos":
    st.header("Gerenciamento de Produtos (Linha de Laticínios)")

    if perfil_atual == "Administrador":
        abas_prod = st.tabs(["➕ Cadastrar Novo Produto", "✏️ Editar ou Excluir Produtos"])
        aba_prod_cad, aba_prod_ger = abas_prod[0], abas_prod[1]
    else:
        aba_prod_cad = st.container()
        aba_prod_ger = None
        st.info("ℹ️ Perfil Funcionário: Acesso permitido apenas para cadastrar novos produtos.")

    with aba_prod_cad:
        with st.form("form_produto"):
            col1, col2, col3 = st.columns(3)
            with col1:
                nome_produto = st.text_input("Nome do Produto (Ex: Iogurte Grego 400g)")
            with col2:
                categoria = st.selectbox("Categoria", ["Iogurtes", "Queijos", "Leites", "Requeijão / Cremes", "Manteiga", "Outros"])
            with col3:
                unidade_medida = st.selectbox("Unidade", ["un", "caixa", "kg", "litros"])

            submitted_prod = st.form_submit_button("Cadastrar Produto")
            if submitted_prod:
                if not nome_produto:
                    st.error("Informe o nome do produto.")
                else:
                    try:
                        supabase.table("produtos").insert({
                            "nome_produto": nome_produto,
                            "categoria": categoria,
                            "unidade_medida": unidade_medida,
                        }).execute()
                        st.success(f"Produto '{nome_produto}' cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")

    if aba_prod_ger is not None:
        with aba_prod_ger:
            st.subheader("Gerenciar Produtos Cadastrados")
            produtos_cadastrados = get_produtos()
            if not produtos_cadastrados:
                st.info("Nenhum produto cadastrado.")
            else:
                prod_dict_ger = {p["nome_produto"]: p for p in produtos_cadastrados}
                escolha_prod = st.selectbox("Selecione o Produto", list(prod_dict_ger.keys()))
                prod_selecionado = prod_dict_ger[escolha_prod]

                with st.form("form_edita_produto"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        novo_nome = st.text_input("Nome do Produto", value=prod_selecionado["nome_produto"])
                    with col2:
                        categorias_lista = ["Iogurtes", "Queijos", "Leites", "Requeijão / Cremes", "Manteiga", "Outros"]
                        cat_atual = prod_selecionado["categoria"] if prod_selecionado["categoria"] in categorias_lista else "Iogurtes"
                        nova_cat = st.selectbox("Categoria", categorias_lista, index=categorias_lista.index(cat_atual))
                    with col3:
                        unidades_lista = ["un", "caixa", "kg", "litros"]
                        un_atual = prod_selecionado["unidade_medida"] if prod_selecionado["unidade_medida"] in unidades_lista else "un"
                        nova_unidade = st.selectbox("Unidade", unidades_lista, index=unidades_lista.index(un_atual))

                    atualizar_p = st.form_submit_button("💾 Salvar Alterações no Produto")

                    if atualizar_p:
                        try:
                            supabase.table("produtos").update({
                                "nome_produto": novo_nome,
                                "categoria": nova_cat,
                                "unidade_medida": nova_unidade
                            }).eq("id", prod_selecionado["id"]).execute()
                            st.success("Produto atualizado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar produto: {e}")

                st.divider()
                if st.button("🗑️ Excluir este Produto", type="secondary"):
                    st.session_state["confirmar_excluir_produto"] = prod_selecionado["id"]

                if st.session_state.get("confirmar_excluir_produto") == prod_selecionado["id"]:
                    st.warning("⚠️ **Tem certeza que deseja excluir este produto?** (Isso removerá também todas as entradas e saídas vinculadas a ele).")
                    col_sim, col_nao = st.columns(2)
                    if col_sim.button("Sim, Excluir Definitivamente", key="sim_del_prod"):
                        try:
                            supabase.table("produtos").delete().eq("id", prod_selecionado["id"]).execute()
                            st.success("Produto excluído com sucesso!")
                            del st.session_state["confirmar_excluir_produto"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
                    if col_nao.button("Cancelar", key="nao_del_prod"):
                        del st.session_state["confirmar_excluir_produto"]
                        st.rerun()


# ==========================================
# 5. GERENCIAMENTO DE USUÁRIOS (EXCLUSIVO ADMIN)
# ==========================================
elif menu == "👥 Gerenciar Usuários":
    st.header("Gerenciamento de Usuários do Sistema")

    if perfil_atual != "Administrador":
        st.error("Acesso negado. Apenas administradores podem gerenciar usuários.")
    else:
        tab_u_cad, tab_u_ger = st.tabs(["➕ Cadastrar Novo Usuário", "✏️ Editar ou Excluir Usuários"])

        with tab_u_cad:
            with st.form("form_novo_usuario"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    novo_login = st.text_input("Nome de Login")
                with col2:
                    nova_senha = st.text_input("Senha", type="password")
                with col3:
                    novo_perfil = st.selectbox("Perfil de Acesso", ["Funcionário", "Administrador"])

                cadastrar_usuario_btn = st.form_submit_button("Criar Usuário")

                if cadastrar_usuario_btn:
                    if not novo_login or not nova_senha:
                        st.error("Preencha o login e a senha.")
                    else:
                        try:
                            supabase.table("usuarios").insert({
                                "nome_login": novo_login,
                                "senha": nova_senha,
                                "perfil": novo_perfil
                            }).execute()
                            st.success(f"Usuário '{novo_login}' cadastrado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao cadastrar usuário (talvez o login já exista): {e}")

        with tab_u_ger:
            st.subheader("Lista e Gestão de Usuários")
            usuarios_cadastrados = get_usuarios()

            if not usuarios_cadastrados:
                st.info("Nenhum usuário cadastrado.")
            else:
                user_dict = {u["nome_login"]: u for u in usuarios_cadastrados}
                escolha_u = st.selectbox("Selecione o Usuário", list(user_dict.keys()))
                u_selecionado = user_dict[escolha_u]

                with st.form("form_edita_usuario"):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_login = st.text_input("Nome de Login", value=u_selecionado["nome_login"])
                        edit_senha = st.text_input("Nova Senha", value=u_selecionado["senha"])
                    with col2:
                        perfis_disp = ["Funcionário", "Administrador"]
                        p_atual = u_selecionado["perfil"] if u_selecionado["perfil"] in perfis_disp else "Funcionário"
                        edit_perfil = st.selectbox("Perfil", perfis_disp, index=perfis_disp.index(p_atual))

                    salvar_u_btn = st.form_submit_button("💾 Salvar Alterações no Usuário")

                    if salvar_u_btn:
                        try:
                            supabase.table("usuarios").update({
                                "nome_login": edit_login,
                                "senha": edit_senha,
                                "perfil": edit_perfil
                            }).eq("id", u_selecionado["id"]).execute()
                            st.success("Usuário atualizado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar usuário: {e}")

                st.divider()
                if u_selecionado["nome_login"] == "admin":
                    st.info("ℹ️ O usuário Administrador principal (`admin`) não pode ser excluído.")
                else:
                    if st.button("🗑️ Excluir este Usuário", type="secondary"):
                        st.session_state["confirmar_excluir_usuario"] = u_selecionado["id"]

                    if st.session_state.get("confirmar_excluir_usuario") == u_selecionado["id"]:
                        st.warning(f"⚠️ **Tem certeza que deseja excluir o usuário '{u_selecionado['nome_login']}'?**")
                        col_sim, col_nao = st.columns(2)
                        if col_sim.button("Sim, Excluir Definitivamente", key="sim_del_u"):
                            try:
                                supabase.table("usuarios").delete().eq("id", u_selecionado["id"]).execute()
                                st.success("Usuário excluído com sucesso!")
                                del st.session_state["confirmar_excluir_usuario"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")
                        if col_nao.button("Cancelar", key="nao_del_u"):
                            del st.session_state["confirmar_excluir_usuario"]
                            st.rerun()