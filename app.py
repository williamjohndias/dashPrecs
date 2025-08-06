from dotenv import load_dotenv
import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import locale
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# ==============
# CONFIGURAÇÃO
# ==============
load_dotenv()

st.set_page_config(
    page_title="📊 Dashboard Precs | Movimentações Financeiras",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configuração do banco de dados
DB_HOST = os.getenv("DB_HOST", "bdunicoprecs.c50cwuocuwro.sa-east-1.rds.amazonaws.com")
DB_NAME = os.getenv("DB_NAME", "Movimentacoes")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Q62^S7v<yK-\\5LHm2PxQ")
DB_PORT = os.getenv("DB_PORT", "5432")

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)

# locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

# ==============
# FUNÇÕES
# ==============

@st.cache_data(ttl=600, show_spinner=False)
def carregar_dados_movimentacoes(data_inicio=None, data_fim=None):
    query = """
        SELECT id, municipio, data_movimentacao, saldo_anterior_valor, saldo_atualizado_valor
        FROM movimentacoes
        WHERE data_movimentacao IS NOT NULL
    """

    # Filtro inteligente baseado nos parâmetros ou padrão amplo
    if data_inicio and data_fim:
        filtros = [f"data_movimentacao BETWEEN '{data_inicio}' AND '{data_fim}'"]
    else:
        # Filtro padrão: últimos 3 anos para garantir dados suficientes
        from datetime import datetime, timedelta
        data_limite = (datetime.now() - timedelta(days=1095)).strftime('%Y-%m-%d')
        filtros = [f"data_movimentacao >= '{data_limite}'"]

    if filtros:
        query += " AND " + " AND ".join(filtros)

    query += " ORDER BY municipio, data_movimentacao, id"

    df = pd.read_sql(query, engine)
    df = df.dropna(subset=['municipio', 'data_movimentacao']).copy()
    df['data_movimentacao'] = pd.to_datetime(df['data_movimentacao'], errors='coerce')
    df['data_only'] = df['data_movimentacao'].dt.date
    df['municipio'] = df['municipio'].str.strip()
    return df


@st.cache_data(ttl=60, show_spinner=False)
def carregar_dados_brutos():
    query = "SELECT * FROM movimentacoes ORDER BY data_movimentacao DESC, id DESC"
    df = pd.read_sql(query, engine)
    return df

def calcular_saldos(df, data_hoje, data_ref):
    resultados = []

    # Verifica se o DataFrame não está vazio
    if df.empty:
        return pd.DataFrame(columns=['Município', f'Saldo ({data_ref.strftime("%d/%m/%Y")})', 
                                   f'Saldo ({data_hoje.strftime("%d/%m/%Y")})', 'Movimentação'])

    for municipio, grupo in df.groupby('municipio'):
        grupo = grupo.sort_values(['data_only', 'id'])

        # Data referência
        df_ref = grupo[grupo['data_only'] <= data_ref]
        saldo_ref = None
        if not df_ref.empty:
            data_ref_real = df_ref['data_only'].max()
            linhas_ref = df_ref[df_ref['data_only'] == data_ref_real]
            if data_ref_real == data_ref:
                linha = linhas_ref.loc[linhas_ref['id'].idxmin()]
                saldo_ref = linha['saldo_anterior_valor']
            else:
                linha = linhas_ref.loc[linhas_ref['id'].idxmax()]
                saldo_ref = linha['saldo_atualizado_valor']

        # Data hoje
        df_hoje = grupo[grupo['data_only'] <= data_hoje]
        saldo_hoje = None
        if not df_hoje.empty:
            data_hoje_real = df_hoje['data_only'].max()
            linhas_hoje = df_hoje[df_hoje['data_only'] == data_hoje_real]
            linha = linhas_hoje.loc[linhas_hoje['id'].idxmax()]
            saldo_hoje = linha['saldo_atualizado_valor']

        # Diferença
        movimentacao = None
        if saldo_ref is not None and saldo_hoje is not None:
            movimentacao = saldo_ref - saldo_hoje

        resultados.append({
            'Município': municipio,
            f'Saldo ({data_ref.strftime("%d/%m/%Y")})': saldo_ref,
            f'Saldo ({data_hoje.strftime("%d/%m/%Y")})': saldo_hoje,
            'Movimentação': movimentacao
        })

    df_result = pd.DataFrame(resultados)
    
    # Verifica se o DataFrame resultante não está vazio e se a coluna existe
    col_hoje = f'Saldo ({data_hoje.strftime("%d/%m/%Y")})'
    if not df_result.empty and col_hoje in df_result.columns:
        return df_result.sort_values(by=col_hoje, ascending=False)
    else:
        return df_result

def formatar_brl(valor):
    if pd.isna(valor):
        return "-"
    try:
        return locale.currency(valor, grouping=True)
    except:
        # fallback caso locale falhe
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def criar_metricas_resumo(df_resultado):
    """Cria métricas de resumo do dashboard"""
    if df_resultado.empty:
        return 0, 0, 0, 0
        
    total_municipios = len(df_resultado)
    col_valores = [col for col in df_resultado.columns if 'Saldo' in col]
    
    if len(col_valores) >= 2:
        try:
            saldo_total_atual = df_resultado[col_valores[1]].fillna(0).sum()
            saldo_total_ref = df_resultado[col_valores[0]].fillna(0).sum()
            variacao_total = df_resultado['Movimentação'].fillna(0).sum() if 'Movimentação' in df_resultado.columns else 0
        except (KeyError, IndexError):
            saldo_total_atual = saldo_total_ref = variacao_total = 0
    else:
        saldo_total_atual = saldo_total_ref = variacao_total = 0
    
    return total_municipios, saldo_total_atual, saldo_total_ref, variacao_total

def criar_grafico_top_municipios(df_resultado, top_n=10):
    """Cria gráfico dos top municípios por saldo"""
    if df_resultado.empty:
        return None
    
    col_valores = [col for col in df_resultado.columns if 'Saldo' in col]
    if not col_valores:
        return None
    
    df_top = df_resultado.nlargest(top_n, col_valores[-1]).copy()
    
    fig = px.bar(
        df_top,
        x='Município',
        y=col_valores[-1],
        title=f"📈 Top {top_n} Municípios por Saldo Atual",
        color=col_valores[-1],
        color_continuous_scale='viridis'
    )
    
    fig.update_layout(
        height=400,
        xaxis_title="Município",
        yaxis_title="Saldo (R$)",
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    fig.update_xaxes(tickangle=45)
    return fig

def aplicar_css_customizado():
    """Aplica CSS customizado para melhor visual"""
    st.markdown("""
    <style>
    /* Estilo geral */
    .main {
        padding-top: 2rem;
    }
    
    /* Header customizado */
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .header-title {
        color: white;
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .header-subtitle {
        color: #f0f0f0;
        font-size: 1.2rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    /* Cartões de métricas */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
        margin-bottom: 1rem;
        transition: transform 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        color: #333;
        margin-bottom: 0.5rem;
    }
    
    .metric-label {
        color: #666;
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Animação de loading */
    .loading-spinner {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100px;
    }
    
    .spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Seções */
    .section-header {
        background: linear-gradient(90deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2rem;
        font-weight: bold;
        margin: 2rem 0 1rem 0;
    }
    
    /* Responsividade */
    @media (max-width: 768px) {
        .header-title {
            font-size: 2rem;
        }
        .metric-value {
            font-size: 1.8rem;
        }
    }
    
    /* Estilo para dataframes */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# ==============
# INTERFACE
# ==============

def main():
    # CSS customizado
    aplicar_css_customizado()
    
    # Header principal
    st.markdown("""
    <div class="header-container">
        <div class="header-title">📊 Dashboard Precs</div>
        <div class="header-subtitle">💰 Movimentações Financeiras Municipais | Análise Comparativa de Saldos</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Spinner de loading
    with st.spinner('🔄 Carregando dados...'):
        time.sleep(0.5)  # Simula loading
    
    # Seção de filtros de data com design melhorado
    st.markdown('<h2 class="section-header">🕰️ Configuração de Período</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        data_ref = st.date_input(
            "📅 Data de Referência", 
            value=datetime.today().date(),
            help="Data inicial para comparação dos saldos"
        )
    with col2:
        data_hoje = st.date_input(
            "📆 Data Atual", 
            value=datetime.today().date(),
            help="Data final para comparação dos saldos"
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("♾️ Reset", help="Restaurar datas para hoje"):
            st.rerun()

    # Validação das datas
    hoje = datetime.today().date()
    
    if data_hoje < data_ref:
        st.warning("⚠️ A data atual é menor que a data de referência. Ajustando para a mesma data.")
        data_hoje = data_ref

    if data_hoje > hoje:
        st.warning("⚠️ A data atual não pode ser maior que hoje. Ajustando para hoje.")
        data_hoje = hoje
        
    if data_ref > hoje:
        st.warning("⚠️ A data de referência não pode ser maior que hoje. Ajustando para hoje.")
        data_ref = hoje

    # Loading customizado e otimizado
    loading_placeholder = st.empty()
    
    with loading_placeholder.container():
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; padding: 2rem;">
            <div style="text-align: center;">
                <div style="
                    width: 50px; height: 50px; border: 4px solid #f3f3f3;
                    border-top: 4px solid #667eea; border-radius: 50%;
                    animation: spin 1s linear infinite; margin: 0 auto 1rem auto;
                "></div>
                <p style="color: #667eea; font-weight: bold;">💰 Carregando dashboard financeiro...</p>
                <p style="color: #999; font-size: 0.9rem;">Aguarde alguns instantes</p>
            </div>
        </div>
        <style>
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        </style>
        """, unsafe_allow_html=True)
    
    # Carregamento otimizado dos dados baseado nas datas selecionadas
    try:
        # Expandir significativamente o período para garantir dados suficientes
        data_inicio_query = min(data_ref, data_hoje) - pd.DateOffset(days=180)  # 6 meses antes
        data_fim_query = max(data_ref, data_hoje) + pd.DateOffset(days=30)     # 1 mês depois
        
        df = carregar_dados_movimentacoes(data_inicio_query.date(), data_fim_query.date())
        df_resultado = calcular_saldos(df, data_hoje, data_ref)
        
        # Remove loading
        loading_placeholder.empty()
        
        # Debug info
        st.info(f"📊 **Dados carregados:** {len(df)} registros encontrados | Período: {data_inicio_query.date()} a {data_fim_query.date()}")
        
        # Verifica se não há dados para o período
        if df_resultado.empty:
            st.warning("⚠️ Não foram encontrados dados para o período selecionado.")
            if len(df) == 0:
                st.error("❌ Nenhum registro encontrado no banco de dados para este período.")
            else:
                st.info(f"💡 Encontrados {len(df)} registros, mas nenhum para as datas específicas: {data_ref.strftime('%d/%m/%Y')} e {data_hoje.strftime('%d/%m/%Y')}")
            return
            
    except Exception as e:
        loading_placeholder.empty()
        st.error(f"❌ Erro ao carregar dados: {str(e)}")
        st.info("💡 Tente selecionar um período diferente ou verifique a conexão com o banco.")
        return
    
    # Métricas de resumo
    if not df_resultado.empty:
        total_municipios, saldo_atual, saldo_ref, variacao = criar_metricas_resumo(df_resultado)
        
        st.markdown('<h2 class="section-header">📈 Resumo Executivo</h2>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{total_municipios}</div>
                <div class="metric-label">🏢 Municípios</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{formatar_brl(saldo_atual)}</div>
                <div class="metric-label">💰 Saldo Total Atual</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{formatar_brl(saldo_ref)}</div>
                <div class="metric-label">📅 Saldo Referência</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            cor_variacao = "#e74c3c" if variacao < 0 else "#27ae60"
            icone_variacao = "🔻" if variacao < 0 else "🔺"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color: {cor_variacao}">{formatar_brl(variacao)}</div>
                <div class="metric-label">{icone_variacao} Variação Total</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Gráfico dos top municípios
        fig = criar_grafico_top_municipios(df_resultado)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")

    # Filtro por município com design melhorado
    st.markdown('<h2 class="section-header">🗂️ Seleção de Municípios</h2>', unsafe_allow_html=True)
    with st.expander("Selecionar municípios para exibição", expanded=False):
        filtro_busca = st.text_input("🔍 Buscar município")
        municipios_ordenados = df_resultado['Município'].tolist()
        
        if filtro_busca:
            termo = filtro_busca.lower()
            municipios_filtrados = sorted(
                municipios_ordenados,
                key=lambda m: (termo not in m.lower(), m)
            )
        else:
            municipios_filtrados = municipios_ordenados

        if "checkbox_states" not in st.session_state:
            st.session_state.checkbox_states = {m: True for m in municipios_ordenados}
            st.session_state.selecionar_todos = True

        col1, col2 = st.columns(2)
        with col1:
            selecionar_todos = st.checkbox("Selecionar todos", value=st.session_state.selecionar_todos)

        if selecionar_todos != st.session_state.selecionar_todos:
            for m in municipios_filtrados:
                st.session_state.checkbox_states[m] = selecionar_todos
            st.session_state.selecionar_todos = selecionar_todos

        municipios_selecionados = []
        for municipio in municipios_filtrados:
            checked = st.checkbox(municipio, value=st.session_state.checkbox_states.get(municipio, True), key=f"check_{municipio}")
            st.session_state.checkbox_states[municipio] = checked
            if checked:
                municipios_selecionados.append(municipio)

    # Filtrar dataframe para exibição
    df_filtrado = df_resultado[df_resultado['Município'].isin(municipios_selecionados)]

    # Exibição da tabela principal
    st.markdown('<h2 class="section-header">💰 Comparativo Detalhado por Município</h2>', unsafe_allow_html=True)
    
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum município selecionado ou dados disponíveis para o período.")
        return
    col_ref = f"Saldo ({data_ref.strftime('%d/%m/%Y')})"
    col_hoje = f"Saldo ({data_hoje.strftime('%d/%m/%Y')})"

    st.dataframe(
        df_filtrado.style.format({
            col_ref: formatar_brl,
            col_hoje: formatar_brl,
            'Movimentação': formatar_brl
        }).set_properties(**{'text-align': 'right'}),
        use_container_width=True,
        hide_index=True
    )
    st.caption("🔁 Se não houver movimentação exata na data, usa-se o valor mais próximo anterior.")

    # Seção do histórico com tabs
    st.markdown("---")
    st.markdown('<h2 class="section-header">🧾 Histórico Detalhado</h2>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 Movimentações Completas", "📈 Análise Temporal"])
    
    with tab1:
        # Filtros
        municipios_disponiveis = ["Todos"] + sorted(df['municipio'].dropna().unique())
        municipio_filtro = st.selectbox("📍 Município (Histórico Bruto)", municipios_disponiveis)

        # Filtro SQL pelo município
        filtro_sql = f"WHERE municipio = '{municipio_filtro}'" if municipio_filtro != "Todos" else ""

        # Controle de paginação para melhor performance
        st.markdown("📊 **Configurações de Exibição**")
        col1, col2 = st.columns(2)
        with col1:
            limite_registros = st.selectbox("📄 Registros por página", [100, 500, 1000, 2000], index=1)
        with col2:
            ordenacao = st.selectbox("📅 Ordenação", ["Mais recente primeiro", "Mais antigo primeiro"], index=0)
        
        ordem_sql = "DESC" if ordenacao == "Mais recente primeiro" else "ASC"
        
        query_paginada = f"""
            SELECT *
            FROM movimentacoes
            {filtro_sql}
            ORDER BY data_movimentacao {ordem_sql}, id {ordem_sql}
            LIMIT {limite_registros}
        """

        with st.spinner('📋 Carregando registros...'):
            df_bruto = pd.read_sql(query_paginada, engine)

        # Remove duplicados considerando colunas específicas
        colunas_para_deduplicar = ['municipio', 'data_movimentacao', 'lancamento_valor']
        df_bruto = df_bruto.drop_duplicates(subset=colunas_para_deduplicar)

        # Formatação dos valores em BRL
        for col in ['saldo_anterior_valor', 'saldo_atualizado_valor', 'lancamento_valor']:
            if col in df_bruto.columns:
                df_bruto[col] = df_bruto[col].apply(formatar_brl)

        # Info do município selecionado
        if municipio_filtro != "Todos":
            st.info(f"🔍 Exibindo movimentações para: **{municipio_filtro}**")
        else:
            st.info("🔍 Exibindo movimentações para todos os municípios")
        
        # Estatísticas rápidas
        if not df_bruto.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📄 Total de Registros", len(df_bruto))
            with col2:
                data_mais_antiga = df_bruto['data_movimentacao'].min() if 'data_movimentacao' in df_bruto.columns else None
                if data_mais_antiga:
                    st.metric("📅 Data Mais Antiga", pd.to_datetime(data_mais_antiga).strftime('%d/%m/%Y'))
            with col3:
                data_mais_recente = df_bruto['data_movimentacao'].max() if 'data_movimentacao' in df_bruto.columns else None
                if data_mais_recente:
                    st.metric("📆 Data Mais Recente", pd.to_datetime(data_mais_recente).strftime('%d/%m/%Y'))
        
        # Dataframe com melhor styling
        st.dataframe(
            df_bruto, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "data_movimentacao": st.column_config.DateColumn(
                    "Data",
                    format="DD/MM/YYYY",
                ),
            }
        )
    
    with tab2:
        st.markdown("🔄 **Análise temporal em desenvolvimento...**")
        st.info("💡 Funcionalidade para gráficos de tendência temporal será adicionada em breve.")


if __name__ == "__main__":
    main()

