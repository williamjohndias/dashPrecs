from dotenv import load_dotenv
import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import locale

# ==============
# CONFIGURAÇÃO
# ==============
load_dotenv()

st.set_page_config("Comparação de Saldos", layout="wide")
DB_URL = os.getenv("AWS_DB_URL")
engine = create_engine(DB_URL)

# locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

# ==============
# FUNÇÕES
# ==============

@st.cache_data(ttl=600)
def carregar_dados_movimentacoes(data_inicio=None, data_fim=None):
    query = """
        SELECT id, municipio, data_movimentacao, saldo_anterior_valor, saldo_atualizado_valor
        FROM movimentacoes
        WHERE data_movimentacao IS NOT NULL
    """

    # Aplicar filtros de data se fornecidos, senão usar range padrão amplo
    if data_inicio and data_fim:
        query += f" AND data_movimentacao BETWEEN '{data_inicio}' AND '{data_fim}'"
    else:
        # Range amplo para garantir que temos dados históricos suficientes
        query += " AND data_movimentacao BETWEEN '2020-01-01' AND '2030-12-31'"

    query += " ORDER BY municipio, data_movimentacao, id"

    df = pd.read_sql(query, engine)
    df = df.dropna(subset=['municipio', 'data_movimentacao']).copy()
    df['data_movimentacao'] = pd.to_datetime(df['data_movimentacao'], errors='coerce')
    df['data_only'] = df['data_movimentacao'].dt.date
    df['municipio'] = df['municipio'].str.strip()
    return df


@st.cache_data(ttl=10)
def carregar_dados_brutos():
    query = "SELECT * FROM movimentacoes ORDER BY data_movimentacao DESC, id DESC"
    df = pd.read_sql(query, engine)
    return df

def calcular_saldos(df, data_hoje, data_ref):
    resultados = []

    for municipio, grupo in df.groupby('municipio'):
        grupo = grupo.sort_values(['data_only', 'id'])

        # ===============================
        # SALDO NA DATA DE REFERÊNCIA
        # ===============================
        df_ref = grupo[grupo['data_only'] <= data_ref]
        saldo_ref = None
        data_ref_encontrada = None
        
        if not df_ref.empty:
            data_ref_real = df_ref['data_only'].max()
            data_ref_encontrada = data_ref_real
            linhas_ref = df_ref[df_ref['data_only'] == data_ref_real]
            
            # Sempre usar o saldo_atualizado_valor da movimentação mais recente da data
            linha = linhas_ref.loc[linhas_ref['id'].idxmax()]
            saldo_ref = linha['saldo_atualizado_valor']

        # ===============================
        # SALDO NA DATA ATUAL (HOJE)
        # ===============================
        df_hoje = grupo[grupo['data_only'] <= data_hoje]
        saldo_hoje = None
        data_hoje_encontrada = None
        
        if not df_hoje.empty:
            data_hoje_real = df_hoje['data_only'].max()
            data_hoje_encontrada = data_hoje_real
            linhas_hoje = df_hoje[df_hoje['data_only'] == data_hoje_real]
            
            # Sempre usar o saldo_atualizado_valor da movimentação mais recente da data
            linha = linhas_hoje.loc[linhas_hoje['id'].idxmax()]
            saldo_hoje = linha['saldo_atualizado_valor']

        # ===============================
        # CÁLCULO DA MOVIMENTAÇÃO
        # ===============================
        movimentacao = None
        if saldo_ref is not None and saldo_hoje is not None:
            movimentacao = saldo_hoje - saldo_ref  # Invertido: positivo = aumento, negativo = diminuição

        resultados.append({
            'Município': municipio,
            f'Saldo ({data_ref.strftime("%d/%m/%Y")})': saldo_ref,
            f'Data Ref Real': data_ref_encontrada,
            f'Saldo ({data_hoje.strftime("%d/%m/%Y")})': saldo_hoje,
            f'Data Hoje Real': data_hoje_encontrada,
            'Movimentação': movimentacao
        })

    df_result = pd.DataFrame(resultados)
    col_hoje = f'Saldo ({data_hoje.strftime("%d/%m/%Y")})'
    return df_result.sort_values(by=col_hoje, ascending=False)

def formatar_brl(valor):
    if pd.isna(valor):
        return "-"
    try:
        return locale.currency(valor, grouping=True)
    except:
        # fallback caso locale falhe
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==============
# INTERFACE
# ==============

def main():
    st.title("💰 Comparativo de Saldos por Município")
    
    # Debug: Mostrar range de datas disponíveis
    with st.expander("🔍 Debug - Informações do Banco de Dados"):
        try:
            query_debug = """
                SELECT 
                    MIN(data_movimentacao) as data_min,
                    MAX(data_movimentacao) as data_max,
                    COUNT(*) as total_registros,
                    COUNT(DISTINCT municipio) as total_municipios
                FROM movimentacoes 
                WHERE data_movimentacao IS NOT NULL
            """
            df_debug = pd.read_sql(query_debug, engine)
            st.write("**Range de datas disponíveis:**", df_debug.iloc[0]['data_min'], "até", df_debug.iloc[0]['data_max'])
            st.write("**Total de registros:**", df_debug.iloc[0]['total_registros'])
            st.write("**Total de municípios:**", df_debug.iloc[0]['total_municipios'])
        except Exception as e:
            st.error(f"Erro ao carregar informações debug: {e}")

    col1, col2 = st.columns(2)
    with col1:
        data_ref = st.date_input("📅 Data de Referência (comparação)", value=datetime.today().date())
    with col2:
        data_hoje = st.date_input("📆 Data Atual (hoje)", value=datetime.today().date())

    # Expandir o range de busca para garantir dados históricos
    data_inicio_busca = min(data_ref, data_hoje) - pd.Timedelta(days=30)  # 30 dias antes
    data_fim_busca = max(data_ref, data_hoje) + pd.Timedelta(days=1)      # 1 dia depois

    # Validação das datas
    if data_hoje < data_ref:
        st.warning("⚠️ A data atual é menor que a data de referência.")

    if data_hoje > datetime.today().date():
        st.warning("⚠️ A data atual não pode ser maior que a data de hoje. Ajustando para hoje.")
        data_hoje = datetime.today().date()

    # Carregar dados com range expandido
    st.info(f"🔄 Buscando dados de {data_inicio_busca.strftime('%d/%m/%Y')} até {data_fim_busca.strftime('%d/%m/%Y')}")
    
    try:
        df = carregar_dados_movimentacoes(data_inicio_busca, data_fim_busca)
        
        if df.empty:
            st.error("❌ Nenhum dado encontrado no período especificado!")
            return
            
        st.success(f"✅ Carregados {len(df)} registros de {df['municipio'].nunique()} municípios")
        
        # Debug: Mostrar dados carregados
        with st.expander("🔍 Debug - Dados Carregados"):
            st.write(f"**Período dos dados:** {df['data_only'].min()} até {df['data_only'].max()}")
            st.write("**Primeiros registros:**")
            st.dataframe(df.head())
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        return

    df_resultado = calcular_saldos(df, data_hoje, data_ref)

    # Debug: Mostrar cálculos
    with st.expander("🔍 Debug - Resultados dos Cálculos"):
        st.dataframe(df_resultado)

    # Filtro por município
    st.markdown("### 🗂️ Filtro por Município")
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

    # Filtrar dataframe para exibição (sem colunas de debug)
    colunas_exibicao = ['Município', f'Saldo ({data_ref.strftime("%d/%m/%Y")})', 
                       f'Saldo ({data_hoje.strftime("%d/%m/%Y")})', 'Movimentação']
    df_filtrado = df_resultado[df_resultado['Município'].isin(municipios_selecionados)][colunas_exibicao]

    # Exibição da tabela
    st.markdown("## 💰 Comparativo de Saldos por Município")
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
    st.caption("🔁 Usa-se sempre o saldo mais recente da data mais próxima anterior ou igual à data solicitada.")

    # ===================
    # HISTÓRICO BRUTO 
    # ===================
    st.markdown("---")
    st.markdown("## 🧾 Histórico Completo de Movimentações")

    # Filtros
    municipios_disponiveis = ["Todos"] + sorted(df['municipio'].dropna().unique())
    municipio_filtro = st.selectbox("📍 Município (Histórico Bruto)", municipios_disponiveis)

    # Filtro SQL pelo município
    filtro_sql = f"WHERE municipio = '{municipio_filtro}'" if municipio_filtro != "Todos" else ""

    query_paginada = f"""
        SELECT *
        FROM movimentacoes
        {filtro_sql}
        ORDER BY data_movimentacao DESC, id DESC
        LIMIT 1000
    """

    try:
        df_bruto = pd.read_sql(query_paginada, engine)

        # Remove duplicados considerando colunas específicas
        colunas_para_deduplicar = ['municipio', 'data_movimentacao', 'lancamento_valor']
        df_bruto = df_bruto.drop_duplicates(subset=colunas_para_deduplicar)

        # Formatação dos valores em BRL
        for col in ['saldo_anterior_valor', 'saldo_atualizado_valor', 'lancamento_valor']:
            if col in df_bruto.columns:
                df_bruto[col] = df_bruto[col].apply(formatar_brl)

        st.markdown(f"🔍 | Município: **{municipio_filtro}**")
        st.dataframe(df_bruto, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")


if __name__ == "__main__":
    main()
