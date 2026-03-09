"""
app.py - Streamlit version of Hytron Coke Analysis

Original Dash app by: Diego Queiroz Faria de Menezes (Firjan SENAI)
Converted to Streamlit for cloud deployment via Streamlit Cloud + GitHub.

Description:
Interactive thermodynamic analysis of carbon deposition and gas composition
from ethanol steam reforming simulations (Aspen Plus v15 - Gibbs free energy).
"""

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Constants ──────────────────────────────────────────────────────────────────
BASE_SHEET        = "SRKKD_SOLIDS"
EXPECTED_PRESSURES = [1.0, 5.0, 10.0, 20.0]
ZERO_CARBON_TOL   = 1e-6

PRESSURE_COLORS = {1.0: "#0057a8", 5.0: "#00a0df", 10.0: "#d71920", 20.0: "#5b6b7a"}
PRESSURE_SURFACE_COLORS = {
    1.0:  [[0.0, "#dbeeff"], [1.0, "#0057a8"]],
    5.0:  [[0.0, "#dcf7ee"], [1.0, "#0b9b6d"]],
    10.0: [[0.0, "#ffe8c8"], [1.0, "#f28c28"]],
    20.0: [[0.0, "#ffd9d9"], [1.0, "#c61b22"]],
}
PRESSURE_SURFACE_BASE_COLOR = {1.0: "#0057a8", 5.0: "#0b9b6d", 10.0: "#f28c28", 20.0: "#c61b22"}
PRESSURE_DASH   = {1.0: "solid", 5.0: "dot", 10.0: "dash", 20.0: "longdash"}
SPECIES_SERIES  = [
    ("h2_kmol_h",  "H2",  "#355f93"),
    ("h2o_kmol_h", "H2O", "#000000"),
    ("co_kmol_h",  "CO",  "#808080"),
    ("co2_kmol_h", "CO2", "#c00000"),
    ("ch4_kmol_h", "CH4", "#12a14a"),
]
REQUIRED_COLUMNS = [
    "s_etoh", "temperature_c", "pressure_bar",
    "carbon_kg_h", "h2_kmol_h", "h2o_kmol_h",
    "co_kmol_h",  "co2_kmol_h", "ch4_kmol_h",
]


# ── Data helpers ───────────────────────────────────────────────────────────────
def _clean_name(name: str) -> str:
    return " ".join(str(name).replace("\n", " ").split()).strip().lower()

def _pick_column(columns, keywords):
    norm = {_clean_name(c): c for c in columns}
    for clean, orig in norm.items():
        if all(k in clean for k in keywords):
            return orig
    for clean, orig in norm.items():
        if any(k in clean for k in keywords):
            return orig
    raise KeyError(f"Column not found for keywords: {keywords}")

def _pick_species_column(columns, species):
    sp = species.lower()
    norm = {_clean_name(c): c for c in columns}
    for clean, orig in norm.items():
        base = clean.split("[", 1)[0].strip()
        if base == sp:
            return orig
    for clean, orig in norm.items():
        if clean.startswith(sp + " ") or clean.startswith(sp + "["):
            return orig
    raise KeyError(f"Species column not found: {species}")


@st.cache_data
def load_thermo_data(uploaded_file) -> pd.DataFrame:
    """Load and standardize the Excel data. Cached so it only runs once per file."""
    frame = pd.read_excel(uploaded_file, sheet_name=BASE_SHEET)
    frame = frame.rename(columns={
        _pick_column(frame.columns.tolist(), ["steam", "ethanol"]): "s_etoh",
        _pick_column(frame.columns.tolist(), ["temperature"]):      "temperature_c",
        _pick_column(frame.columns.tolist(), ["pressure"]):         "pressure_bar",
        _pick_column(frame.columns.tolist(), ["carbon"]):           "carbon_kg_h",
        _pick_species_column(frame.columns.tolist(), "h2"):         "h2_kmol_h",
        _pick_species_column(frame.columns.tolist(), "h2o"):        "h2o_kmol_h",
        _pick_species_column(frame.columns.tolist(), "co"):         "co_kmol_h",
        _pick_species_column(frame.columns.tolist(), "co2"):        "co2_kmol_h",
        _pick_species_column(frame.columns.tolist(), "ch4"):        "ch4_kmol_h",
    })
    data = frame[REQUIRED_COLUMNS].apply(pd.to_numeric, errors="coerce").dropna()
    data = data[data["pressure_bar"].isin(EXPECTED_PRESSURES)].copy()
    return data


# ── Figure builders ────────────────────────────────────────────────────────────
def build_carbon_3d_figure(data, pressures, opacity) -> go.Figure:
    fig = go.Figure()
    carbon_max = float(data["carbon_kg_h"].max()) if not data.empty else 1.0

    for pressure in sorted(pressures):
        subset = data[data["pressure_bar"] == pressure]
        if subset.empty:
            continue
        pivot = (
            subset.pivot_table(index="temperature_c", columns="s_etoh",
                               values="carbon_kg_h", aggfunc="mean")
            .sort_index().sort_index(axis=1)
        )
        fig.add_trace(go.Surface(
            x=pivot.columns.values, y=pivot.index.values, z=pivot.values,
            name=f"P = {pressure:g} bar",
            legendgroup=f"surface_p{pressure:g}",
            showlegend=False, opacity=opacity,
            colorscale=PRESSURE_SURFACE_COLORS.get(float(pressure), "Viridis"),
            cmin=0, cmax=carbon_max, showscale=False,
            hovertemplate=(
                "S/EtOH: %{x:.2f}<br>Temperatura: %{y:.2f} °C<br>"
                f"Carbono: %{{z:.4f}} kg/h<br>Pressao: {pressure:g} bar<extra></extra>"
            ),
        ))

    for pressure in sorted(pressures):
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None], mode="markers",
            name=f"P = {pressure:g} bar",
            legendgroup=f"surface_p{pressure:g}", showlegend=True,
            marker=dict(size=8, color=PRESSURE_SURFACE_BASE_COLOR.get(float(pressure), "#555"), symbol="square"),
            hoverinfo="skip",
        ))

    fig.update_layout(
        template="plotly_white",
        scene=dict(
            xaxis_title="S/EtOH ratio", yaxis_title="Temp [°C]", zaxis_title="Carbon [kg/h]",
            camera=dict(eye=dict(x=1.3, y=1.6, z=0.54), center=dict(x=0.02, y=0.03, z=-0.2), up=dict(x=0, y=0, z=1)),
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        title=dict(text="Deposicao de carbono", x=0.5, xanchor="center"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.01),
        height=600,
    )
    return fig


def build_zero_plane_figure(data, pressures) -> go.Figure:
    fig = go.Figure()

    for pressure in sorted(pressures):
        subset = data[data["pressure_bar"] == pressure].copy()
        if subset.empty:
            continue
        pivot = (
            subset.pivot_table(index="temperature_c", columns="s_etoh",
                               values="carbon_kg_h", aggfunc="mean")
            .sort_index().sort_index(axis=1)
        )
        if pivot.empty:
            continue

        color       = PRESSURE_COLORS.get(float(pressure), None)
        legend_name = f"P = {pressure:g} bar"
        zero_pts    = subset[subset["carbon_kg_h"] <= ZERO_CARBON_TOL]

        if not zero_pts.empty:
            fig.add_trace(go.Scatter(
                x=zero_pts["s_etoh"], y=zero_pts["temperature_c"],
                mode="markers", name=legend_name,
                legendgroup=f"zero_p{pressure:g}", showlegend=True,
                marker=dict(size=8, color=color, opacity=0.22, line=dict(width=1, color=color)),
                hovertemplate=(
                    "S/EtOH: %{x:.2f}<br>Temperatura: %{y:.2f} °C<br>"
                    f"Pressao: {pressure:g} bar<br>Carbono ~ 0 kg/h<extra></extra>"
                ),
            ))

        if pivot.shape[0] > 1 and pivot.shape[1] > 1:
            fig.add_trace(go.Contour(
                x=pivot.columns.values, y=pivot.index.values,
                z=(pivot.values > ZERO_CARBON_TOL).astype(float),
                name=f"Limite {legend_name}",
                legendgroup=f"zero_p{pressure:g}", showlegend=False, showscale=False,
                contours=dict(start=0.5, end=0.5, size=1, coloring="none", showlabels=False),
                line=dict(color=color, width=2.5),
                hoverinfo="skip",
            ))

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=45, r=20, t=42, b=45),
        title=dict(text="Plano Carbon = 0", x=0.5, xanchor="center"),
        xaxis=dict(title="S/EtOH ratio"), yaxis=dict(title="Temp [°C]"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.01),
        height=450,
    )
    return fig


def build_species_figure(data, pressures, selected_ratio) -> go.Figure:
    fig = go.Figure()

    if selected_ratio is None:
        fig.update_layout(title="Vazoes molares vs temperatura", template="plotly_white", height=480)
        return fig

    ratio_data = data[data["s_etoh"] == selected_ratio].copy()

    for pressure in sorted(pressures):
        subset = ratio_data[ratio_data["pressure_bar"] == pressure].sort_values("temperature_c")
        if subset.empty:
            continue
        dash_style = PRESSURE_DASH.get(float(pressure), "solid")
        for col, label, color in SPECIES_SERIES:
            if col not in subset.columns or subset[col].isna().all():
                continue
            fig.add_trace(go.Scatter(
                x=subset["temperature_c"], y=subset[col],
                mode="lines+markers",
                name=f"{label} | P={pressure:g} bar",
                legendgroup=f"{label}_p{pressure:g}",
                line=dict(color=color, width=2, dash=dash_style),
                marker=dict(size=5, color=color),
                hovertemplate=(
                    "Temp: %{x:.2f} °C<br>"
                    f"{label}: %{{y:.4f}} kmol/h<br>"
                    f"Pressao: {pressure:g} bar<br>"
                    f"S/EtOH: {selected_ratio:g}<extra></extra>"
                ),
            ))

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=50, r=20, t=44, b=50),
        title=dict(text=f"Vazoes molares vs temperatura (S/EtOH = {selected_ratio:g})", x=0.5, xanchor="center"),
        xaxis=dict(title="Temperatura [°C]"), yaxis=dict(title="Vazao molar [kmol/h]"),
        legend=dict(orientation="v", yanchor="top", y=0.98, xanchor="left", x=1.02),
        height=520,
    )
    return fig


# ── Streamlit app ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hytron Coke Analysis - Firjan SENAI",
    page_icon="🔬",
    layout="wide",
)

# Header
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("Análise termodinâmica de carbono")
    st.caption(
        "Deposição de carbono no processo de reforma a vapor de etanol "
        "(Aspen Plus v15 → Energia livre de Gibbs)."
    )
with col_logo:
    logo_path = Path(__file__).resolve().parent / "assets" / "logo-firjan-senai.png"
    if logo_path.exists():
        st.image(str(logo_path), width=180)

st.divider()

# File upload
uploaded_file = st.file_uploader(
    "📂 Upload do arquivo Excel (Coke_Analysis_AspenPlusV15.xlsx)",
    type=["xlsx"],
    help="O arquivo deve conter a aba 'SRKKD_SOLIDS'.",
)

if uploaded_file is None:
    st.info("👆 Faça o upload do arquivo Excel para iniciar a análise.")
    st.stop()

# Load data
try:
    data = load_thermo_data(uploaded_file)
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

available_pressures = [p for p in EXPECTED_PRESSURES if p in data["pressure_bar"].unique()]
available_ratios    = sorted(float(v) for v in data["s_etoh"].dropna().unique())

# ── Section 1: Carbon deposition (3D + 2D) ────────────────────────────────────
st.subheader("🧊 Deposição de Carbono")

ctrl1, ctrl2 = st.columns(2)
with ctrl1:
    selected_pressures_3d = st.multiselect(
        "Pressão [bar]",
        options=available_pressures,
        default=[p for p in available_pressures if p in (1.0, 20.0)],
        format_func=lambda p: f"P = {p:g} bar",
        key="pressures_3d",
    )
with ctrl2:
    opacity = st.slider(
        "Opacidade das superfícies",
        min_value=0.2, max_value=1.0, step=0.05, value=0.6,
        key="opacity",
    )

pressures_3d = selected_pressures_3d or available_pressures

st.plotly_chart(build_carbon_3d_figure(data, pressures_3d, opacity), use_container_width=True)
st.plotly_chart(build_zero_plane_figure(data, pressures_3d),          use_container_width=True)

# ── Section 2: Species vs Temperature ─────────────────────────────────────────
st.divider()
st.subheader("📈 Vazões Molares vs Temperatura")

ctrl3, ctrl4 = st.columns(2)
with ctrl3:
    selected_pressures_sp = st.multiselect(
        "Pressão [bar] - gráfico de vazões",
        options=available_pressures,
        default=[p for p in available_pressures if p in (1.0, 20.0)],
        format_func=lambda p: f"P = {p:g} bar",
        key="pressures_species",
    )
with ctrl4:
    ratio_index = available_ratios.index(min(available_ratios, key=lambda r: abs(r - 1.0)))
    selected_ratio = st.select_slider(
        "S/EtOH ratio - gráfico de vazões",
        options=available_ratios,
        value=available_ratios[ratio_index],
        format_func=lambda r: f"{r:.2f}",
        key="ratio_slider",
    )

pressures_sp = selected_pressures_sp or available_pressures
st.plotly_chart(build_species_figure(data, pressures_sp, selected_ratio), use_container_width=True)

st.caption("Firjan SENAI · Hytron (Neuman-Esser) · USP · Shell")
