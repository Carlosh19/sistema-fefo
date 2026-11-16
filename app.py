from datetime import date
import pandas as pd
import streamlit as st
from supabase import create_client

# Configuração da Página
st.set_page_config(
    page_title="Controle FEFO - Laticínios", page_icon="🧀", layout="wide"
)

# --- CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


supabase = init_connection()

# --- FUNÇÕES DE BANCO DE DADOS ---
def get_produtos():
    response = supabase.table("produtos").select("*").execute()
    return response.data


def get_estoque_fefo():
    response = supabase.table("vw_estoque_fefo").select("*").execute()
    return response.data


def get_saidas():
    response = supabase.table("saidas").select("*, entradas(numero_lote, produtos(nome_produto))").execute()
    return response.data


# --- CABEÇALHO DO APLICATIVO ---
st.title("🧀 Controle de Estoque & Expedição FEFO")
st.markdown(
    "Gerenciamento inteligente de laticínios baseado no critério **Primeiro que Vence, Primeiro que Sai (FEFO)**."
)

# Menu Lateral (Abas do Sistema)
menu = st.sidebar.selectbox(
    "Navegação",
    [
        "📊 Painel FEFO & Estoque",
        "📥 Registrar Entrada (Recebimento)",
        "🚚 Registrar Saída (Expedição)",
        "📋 Cadastro de Produtos",
    ],
)

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

        # Métricas no Topo
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

        # Filtro de status
        status_filter = st.selectbox(
            "Filtrar por Status FEFO",
            ["Todos", "Crítico (<= 7d)", "Atenção (8-15d)", "Seguro (> 15d)"],
        )

        if status_filter != "Todos":
            df_filtered = df[df["status_fefo"] == status_filter]
        else:
            df_filtered = df

        # Tabela formatada
        st.subheader("Fila de Expedição FEFO (Prioridade por Vencimento)")
        
        # Renomear colunas para exibição amigável
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
# 2. REGISTRAR ENTRADA
# ==========================================
elif menu == "📥 Registrar Entrada (Recebimento)":
    st.header("Recebimento de Nova Carga / Lote")

    produtos = get_produtos()
    if not produtos:
        st.warning("Cadastre produtos primeiro na aba 'Cadastro de Produtos'.")
    else:
        produto_dict = {p["nome_produto"]: p["id"] for p in produtos}

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
                    st.error("Por favor, preencha todos os campos obrigatórios.")
                else:
                    produto_id = produto_dict[produto_selecionado]
                    try:
                        supabase.table("entradas").insert(
                            {
                                "data_entrada": str(data_entrada),
                                "numero_lote": numero_lote,
                                "produto_id": produto_id,
                                "quantidade_recebida": int(quantidade_recebida),
                                "data_validade": str(data_validade),
                                "fornecedor": fornecedor,
                                "nota_fiscal": nota_fiscal,
                            }
                        ).execute()
                        st.success("Entrada registrada com sucesso! Estoque atualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

# ==========================================
# 3. REGISTRAR SAÍDA (EXPEDIÇÃO)
# ==========================================
elif menu == "🚚 Registrar Saída (Expedição)":
    st.header("Expedição de Mercadoria para os Mercados")
    st.markdown("O sistema prioriza automaticamente os lotes com vencimento mais próximo (FEFO).")

    estoque = get_estoque_fefo()

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
                # Criar opções amigáveis listando o lote, produto e saldo disponível ordenados por validade
                lotes_opcoes = {
                    f"Lote: {item['numero_lote']} | {item['nome_produto']} | Validade: {item['data_validade']} (Saldo: {item['saldo_atual']} un)": item
                    for item in estoque
                }
                lote_escolhido_str = st.selectbox("Selecione o Lote (Ordenado por FEFO)", list(lotes_opcoes.keys()))
                
                lote_selecionado = lotes_opcoes[lote_escolhido_str]
                max_qtd = lote_selecionado["saldo_atual"]

                quantidade_expedida = st.number_input(
                    f"Quantidade a Expedir (Disponível no lote: {max_qtd})",
                    min_value=1,
                    max_value=int(max_qtd),
                    step=1,
                )

            submitted_saida = st.form_submit_button("Confirmar Expedição")

            if submitted_saida:
                if not cliente_mercado or not numero_pedido:
                    st.error("Preencha o nome do mercado e o número do pedido.")
                else:
                    try:
                        supabase.table("saidas").insert(
                            {
                                "data_saida": str(data_saida),
                                "entrada_id": int(lote_selecionado["entrada_id"]),
                                "quantidade_expedida": int(quantidade_expedida),
                                "cliente_mercado": cliente_mercado,
                                "numero_pedido": numero_pedido,
                            }
                        ).execute()
                        st.success("Saída expedida e baixa realizada com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao registrar saída: {e}")

        st.divider()
        st.subheader("Histórico de Expedições Recentes")
        saidas = get_saidas()
        if saidas:
            df_saidas = pd.DataFrame(saidas)
            # Organizar colunas de exibição
            df_saidas_show = []
            for s in saidas:
                df_saidas_show.append({
                    "Data Saída": s["data_saida"],
                    "Cliente/Mercado": s["cliente_mercado"],
                    "Pedido": s["numero_pedido"],
                    "Produto": s["entradas"]["produtos"]["nome_produto"] if s.get("entradas") else "N/A",
                    "Lote": s["entradas"]["numero_lote"] if s.get("entradas") else "N/A",
                    "Qtd Expedida": s["quantidade_expedida"]
                })
            st.dataframe(pd.DataFrame(df_saidas_show), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma saída registrada ainda.")

# ==========================================
# 4. CADASTRO DE PRODUTOS
# ==========================================
elif menu == "📋 Cadastro de Produtos":
    st.header("Gerenciamento de Produtos (Linha de Laticínios)")

    with st.form("form_produto"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nome_produto = st.text_input("Nome do Produto (Ex: Iogurte Grego Tradicional 400g)")
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
                    supabase.table("produtos").insert(
                        {
                            "nome_produto": nome_produto,
                            "categoria": categoria,
                            "unidade_medida": unidade_medida,
                        }
                    ).execute()
                    st.success(f"Produto '{nome_produto}' cadastrado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cadastrar (talvez já exista): {e}")

    st.divider()
    st.subheader("Produtos Cadastrados")
    produtos_cadastrados = get_produtos()
    if produtos_cadastrados:
        df_prod = pd.DataFrame(produtos_cadastrados)[["nome_produto", "categoria", "unidade_medida", "created_at"]]
        df_prod.columns = ["Produto", "Categoria", "Unidade", "Cadastrado em"]
        st.dataframe(df_prod, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto cadastrado.")