"""
Interface Streamlit para a biblioteca `baseflow` (separação de baseflow).
Permite buscar dados direto da ANA (via hydrobr) ou subir um CSV,
escolher entre os métodos de separação e visualizar/baixar os resultados.

Para rodar:
    pip install -r requirements.txt
    streamlit run app.py
"""

import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import baseflow

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
st.set_page_config(page_title="Separação de Baseflow", page_icon="💧", layout="wide")

ALL_METHODS = [
    "UKIH", "Local", "Fixed", "Slide", "LH", "Chapman",
    "CM", "Boughton", "Furey", "Eckhardt", "EWMA", "Willems",
]

METHODS_NEED_AREA = {"Fixed", "Local", "Slide"}

if "df" not in st.session_state:
    st.session_state["df"] = None
if "station_label" not in st.session_state:
    st.session_state["station_label"] = "Q"

st.title("💧 Separação de Baseflow")
st.caption(
    "Interface para a biblioteca `baseflow` (Xie et al., 2020) — "
    "12 métodos de separação de escoamento de base, com calibração automática."
)

# ---------------------------------------------------------------------
# Sidebar — 1. Fonte dos dados
# ---------------------------------------------------------------------
st.sidebar.header("1. Dados de vazão")
source = st.sidebar.radio(
    "Fonte dos dados",
    ["Estação da ANA (Hidroweb)", "Upload de CSV"],
    label_visibility="collapsed",
)

lat_val, lon_val, area_val = -15.0, -47.0, 1000.0

if source == "Estação da ANA (Hidroweb)":
    st.sidebar.caption(
        "Usa o pacote **hydrobr**, que consulta a base da ANA. "
        "Requer conexão com a internet."
    )
    codigo = st.sidebar.text_input("Código da estação (8 dígitos)", placeholder="ex: 56850000")
    only_consisted = st.sidebar.checkbox("Somente dados consistidos", value=False)

    if st.sidebar.button("🔎 Buscar dados na ANA", width='stretch'):
        if not codigo.strip():
            st.sidebar.error("Informe o código da estação.")
        else:
            try:
                import hydrobr
            except ImportError:
                st.sidebar.error(
                    "Pacote `hydrobr` não instalado. Rode: `pip install hydrobr`"
                )
                hydrobr = None

            if "hydrobr" in dir() and hydrobr is not None:
                with st.spinner("Baixando série histórica da ANA..."):
                    try:
                        data = hydrobr.get_data.ANA.flow_data(
                            [codigo.strip()], only_consisted=only_consisted
                        )
                        col = data.columns[0]
                        series = data[col].dropna()
                        df = series.to_frame(name=str(codigo.strip()))
                        df.index.name = "date"
                        st.session_state["df"] = df
                        st.session_state["station_label"] = str(codigo.strip())
                        st.sidebar.success(f"{len(df)} registros baixados.")
                    except Exception as e:
                        st.sidebar.error(f"Erro ao buscar dados: {e}")

    # Tentativa de trazer metadados (lat/lon/área) do inventário da ANA
    if st.session_state["df"] is not None and st.sidebar.checkbox(
        "Buscar lat/lon/área da estação automaticamente", value=True
    ):
        try:
            import hydrobr
            inv = hydrobr.get_data.ANA.list_flow_stations()
            row = inv[inv["Code"].astype(str) == st.session_state["station_label"]]
            if not row.empty:
                lat_val = float(row.iloc[0].get("Latitude", lat_val))
                lon_val = float(row.iloc[0].get("Longitude", lon_val))
                area_val = float(row.iloc[0].get("DrainageArea", area_val)) or area_val
        except Exception:
            pass  # cai para os valores padrão / manuais abaixo

else:
    uploaded = st.sidebar.file_uploader("Arquivo CSV", type=["csv"])
    st.sidebar.caption("O CSV precisa ter uma coluna de data e uma de vazão (m³/s).")
    if uploaded is not None:
        raw = pd.read_csv(uploaded)
        cols = list(raw.columns)
        c1, c2 = st.sidebar.columns(2)
        date_col = c1.selectbox("Coluna de data", cols, index=0)
        flow_col = c2.selectbox(
            "Coluna de vazão", cols, index=min(1, len(cols) - 1)
        )
        sep_decimal = st.sidebar.selectbox("Separador decimal do CSV", [".", ","], index=0)
        if st.sidebar.button("Carregar CSV", width='stretch'):
            try:
                df_raw = raw[[date_col, flow_col]].copy()
                df_raw[date_col] = pd.to_datetime(df_raw[date_col], dayfirst=True)
                if sep_decimal == ",":
                    df_raw[flow_col] = (
                        df_raw[flow_col].astype(str).str.replace(",", ".").astype(float)
                    )
                df_raw = df_raw.set_index(date_col).sort_index()
                df_raw.index.name = "date"
                df_raw = df_raw.rename(columns={flow_col: "Q"}).dropna()
                st.session_state["df"] = df_raw
                st.session_state["station_label"] = "Q"
                st.sidebar.success(f"{len(df_raw)} registros carregados.")
            except Exception as e:
                st.sidebar.error(f"Erro ao ler CSV: {e}")

st.sidebar.subheader("Metadados da bacia")
st.sidebar.caption("Usados apenas pelos métodos Fixed, Local e Slide.")
lat = st.sidebar.number_input("Latitude", value=lat_val, format="%.4f")
lon = st.sidebar.number_input("Longitude", value=lon_val, format="%.4f")
area = st.sidebar.number_input("Área de drenagem (km²)", value=area_val, min_value=0.1)

# ---------------------------------------------------------------------
# Sidebar — 2. Métodos
# ---------------------------------------------------------------------
st.sidebar.header("2. Métodos de separação")
selected_methods = st.sidebar.multiselect(
    "Escolha um ou mais métodos", ALL_METHODS, default=ALL_METHODS
)
run_btn = st.sidebar.button("▶️ Calcular baseflow", type="primary", width='stretch')

# ---------------------------------------------------------------------
# Corpo principal
# ---------------------------------------------------------------------
df = st.session_state["df"]

if df is None:
    st.info("⬅️ Busque uma estação da ANA ou faça upload de um CSV para começar.")
    st.stop()

station_label = st.session_state["station_label"]

st.subheader("Série de vazão")
fig_raw = go.Figure()
fig_raw.add_trace(
    go.Scatter(x=df.index, y=df.iloc[:, 0], mode="lines", name="Vazão total", line=dict(color="#1f77b4"))
)
fig_raw.update_layout(
    height=300, margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="Data", yaxis_title="Vazão (m³/s)",
)
st.plotly_chart(fig_raw, width='stretch')
st.caption(f"{len(df)} registros · {df.index.min().date()} a {df.index.max().date()}")

if not run_btn:
    st.stop()

if not selected_methods:
    st.warning("Selecione ao menos um método na barra lateral.")
    st.stop()

# ---------------------------------------------------------------------
# Rodar a separação
# ---------------------------------------------------------------------
df_sta = pd.DataFrame(
    {"lon": [lon], "lat": [lat], "area": [area]}, index=[df.columns[0]]
)

with st.spinner("Calculando separação de baseflow..."):
    try:
        dfs, df_kge = baseflow.separation(
            df, df_sta, method=selected_methods, return_kge=True
        )
    except Exception as e:
        st.error(f"Erro ao rodar `baseflow.separation`: {e}")
        st.stop()

# dfs vem como dict {método: DataFrame(data x estações)} — as chaves são os
# NOMES DOS MÉTODOS, não as estações. Montamos um DataFrame único
# (data x método) extraindo a coluna da estação de cada método.
station_key = df.columns[0]

if isinstance(dfs, dict):
    cols = {}
    missing = []
    for method_name, method_df in dfs.items():
        if isinstance(method_df, pd.DataFrame):
            if station_key in method_df.columns:
                cols[method_name] = method_df[station_key]
            elif method_df.shape[1] == 1:
                cols[method_name] = method_df.iloc[:, 0]
            else:
                missing.append(method_name)
        else:
            # já é uma Series
            cols[method_name] = method_df
    if not cols:
        st.error(
            f"Não consegui extrair a estação '{station_key}' de nenhum método. "
            f"Colunas disponíveis (exemplo): "
            f"{list(next(iter(dfs.values())).columns) if dfs else 'N/A'}"
        )
        st.stop()
    result = pd.DataFrame(cols)
else:
    # já é um DataFrame único (data x método)
    result = dfs

# df_kge: normalmente DataFrame com estações no índice e métodos nas colunas
if isinstance(df_kge, pd.DataFrame):
    if station_key in df_kge.index:
        kge_row = df_kge.loc[station_key]
    elif station_key in df_kge.columns:
        kge_row = df_kge[station_key]
    elif len(df_kge) == 1:
        kge_row = df_kge.iloc[0]
    else:
        st.error(
            f"Não encontrei a estação '{station_key}' no KGE. "
            f"Índice: {list(df_kge.index)} · Colunas: {list(df_kge.columns)}"
        )
        st.stop()
else:
    # já é uma Series (uma única estação)
    kge_row = df_kge

# garante que só ficam os métodos realmente presentes em result
kge_row = kge_row.reindex(result.columns).dropna()
best_method = kge_row.idxmax() if not kge_row.empty else result.columns[0]

# ---------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------
st.subheader("Resultado da separação")

tab_plot, tab_kge, tab_table = st.tabs(["📈 Gráfico", "🏆 Desempenho (KGE)", "📋 Tabela"])

with tab_plot:
    show_methods = st.multiselect(
        "Métodos a exibir no gráfico", list(result.columns), default=list(result.columns)
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=df.index, y=df.iloc[:, 0], mode="lines", name="Vazão total",
                    line=dict(color="lightgray", width=1))
    )
    for m in show_methods:
        fig.add_trace(go.Scatter(x=result.index, y=result[m], mode="lines", name=m))
    fig.update_layout(
        height=500, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Data", yaxis_title="Vazão (m³/s)", legend_title="Método",
    )
    st.plotly_chart(fig, width='stretch')

with tab_kge:
    st.write(f"**Melhor método (maior KGE): `{best_method}`**")
    kge_df = kge_row.sort_values(ascending=False).to_frame("KGE")
    st.bar_chart(kge_df)
    st.dataframe(kge_df.style.format("{:.3f}"), width='stretch')
    st.caption(
        "KGE (Kling-Gupta Efficiency) mede o quão bem o baseflow reproduz a curva de "
        "recessão da vazão observada — quanto mais próximo de 1, melhor."
    )

with tab_table:
    bfi = (result.sum() / df.iloc[:, 0].reindex(result.index).sum()).to_frame("BFI médio")
    st.write("**Baseflow Index (BFI) médio por método**")
    st.dataframe(bfi.style.format("{:.3f}"), width='stretch')

    st.write("**Série completa de baseflow por método**")
    st.dataframe(result, width='stretch', height=300)

    csv_buf = io.StringIO()
    result.to_csv(csv_buf)
    st.download_button(
        "⬇️ Baixar resultados (CSV)",
        data=csv_buf.getvalue(),
        file_name=f"baseflow_{station_label}.csv",
        mime="text/csv",
        width='stretch',
    )
