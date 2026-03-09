"""
app.py - General Carbon Deposition Analysis Tool
Firjan SENAI - Hytron Project

Generalized version: works with any thermodynamic system and Excel structure.
User uploads Excel, picks sheet, maps columns, then explores interactive charts.
"""

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Color palettes ─────────────────────────────────────────────────────────────
PRESSURE_COLORS = ["#0057a8", "#00a0df", "#d71920", "#5b6b7a",
                   "#f28c28", "#0b9b6d", "#c61b22", "#8e44ad"]
SPECIES_COLORS  = ["#355f93", "#000000", "#808080", "#c00000",
                   "#12a14a", "#e67e22", "#8e44ad", "#16a085"]
PRESSURE_DASHES = ["solid", "dot", "dash", "longdash",
                   "dashdot", "longdashdot", "solid", "dot"]

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Carbon Analysis Tool - Firjan SENAI",
    page_icon="🔬",
    layout="wide",
)

# ── Header ─────────────────────────────────────────────────────────────────────
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("🔬 Carbon Deposition Analysis Tool")
    st.caption("General thermodynamic analysis tool — supports any reforming system and Excel structure.")
with col_logo:
    logo_path = Path(__file__).resolve().parent / "assets" / "logo-firjan-senai.png"
    if logo_path.exists():
        st.image(str(logo_path), width=180)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — FILE UPLOAD & SHEET SELECTION
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Step 1 — Upload your Excel file")

uploaded_file = st.file_uploader(
    "Upload Excel file (.xlsx)",
    type=["xlsx"],
    help="Any Excel file with tabular thermodynamic data.",
)

if uploaded_file is None:
    st.info("👆 Upload an Excel file to begin.")
    st.stop()

try:
    xl         = pd.ExcelFile(uploaded_file)
    all_sheets = xl.sheet_names
except Exception as e:
    st.error(f"Could not read Excel file: {e}")
    st.stop()

selected_sheet = st.selectbox("Select sheet", options=all_sheets)

@st.cache_data
def load_sheet(file, sheet):
    return pd.read_excel(file, sheet_name=sheet)

try:
    raw_df = load_sheet(uploaded_file, selected_sheet)
except Exception as e:
    st.error(f"Could not load sheet '{selected_sheet}': {e}")
    st.stop()

st.success(f"✅ Loaded **{len(raw_df):,} rows** and **{len(raw_df.columns)} columns** from sheet `{selected_sheet}`.")

with st.expander("Preview raw data (first 5 rows)"):
    st.dataframe(raw_df.head(), use_container_width=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — COLUMN MAPPING
# Note: widget keys use "w_" prefix to avoid conflict with session_state keys
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Step 2 — Map your columns")
st.caption("Tell the app what each column represents. Pressure and Species are optional.")

all_columns = raw_df.columns.tolist()
none_option = "— not applicable —"
col_options = [none_option] + all_columns

c1, c2 = st.columns(2)
with c1:
    w_x_col      = st.selectbox("X axis (e.g. S/CH4 ratio, S/EtOH)", options=all_columns,  key="w_x_col")
    w_carbon_col = st.selectbox("Carbon column (deposition value)",    options=all_columns,  key="w_carbon_col")
with c2:
    w_y_col        = st.selectbox("Y axis (e.g. Temperature)",        options=all_columns,  key="w_y_col")
    w_pressure_col = st.selectbox("Pressure column (optional)",       options=col_options,  key="w_pressure_col")

w_species_cols = st.multiselect(
    "Species columns (optional — e.g. H2, CO, CO2, CH4, H2O)",
    options=all_columns,
    key="w_species_cols",
    help="Select one or more columns representing molar flowrates of gas species.",
)

apply = st.button("▶ Apply Configuration & Build Dashboard", type="primary")

if not apply and "configured" not in st.session_state:
    st.info("👆 Map your columns above then click **Apply Configuration**.")
    st.stop()

# Save to session state only when button is clicked — using different key names
if apply:
    st.session_state.configured    = True
    st.session_state.cfg_x         = w_x_col
    st.session_state.cfg_y         = w_y_col
    st.session_state.cfg_carbon    = w_carbon_col
    st.session_state.cfg_pressure  = w_pressure_col
    st.session_state.cfg_species   = w_species_cols
    st.session_state.cfg_has_pres  = (w_pressure_col != none_option)
    st.session_state.cfg_has_spec  = (len(w_species_cols) > 0)

# Read confirmed config from session state
x_col        = st.session_state.cfg_x
y_col        = st.session_state.cfg_y
carbon_col   = st.session_state.cfg_carbon
pressure_col = st.session_state.cfg_pressure
species_cols = st.session_state.cfg_species
has_pressure = st.session_state.cfg_has_pres
has_species  = st.session_state.cfg_has_spec

# Build working dataframe with only mapped columns
keep_cols = [x_col, y_col, carbon_col]
if has_pressure:
    keep_cols.append(pressure_col)
keep_cols += species_cols

try:
    data = raw_df[keep_cols].apply(pd.to_numeric, errors="coerce").dropna(subset=[x_col, y_col, carbon_col])
except Exception as e:
    st.error(f"Error processing columns: {e}")
    st.stop()

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Step 3 — Explore your data")

if has_pressure:
    available_pressures = sorted(data[pressure_col].dropna().unique().tolist())
else:
    available_pressures = [None]

available_x = sorted(data[x_col].dropna().unique().tolist())
ZERO_TOL    = 1e-6

# ── Controls ───────────────────────────────────────────────────────────────────
ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])

with ctrl1:
    if has_pressure:
        selected_pressures = st.multiselect(
            f"Filter by {pressure_col}",
            options=available_pressures,
            default=available_pressures,
            format_func=lambda p: f"{p:g}",
        )
        if not selected_pressures:
            selected_pressures = available_pressures
    else:
        selected_pressures = [None]

with ctrl2:
    opacity = st.slider("Surface opacity (3D chart)", 0.2, 1.0, 0.6, 0.05)

with ctrl3:
    st.metric("Total rows", f"{len(data):,}")
    st.metric("X values",   f"{len(available_x)}")


# ── Figure builders ────────────────────────────────────────────────────────────
def build_3d_figure(df, pressures, opacity):
    fig        = go.Figure()
    carbon_max = float(df[carbon_col].max()) if not df.empty else 1.0
    iter_p     = sorted(p for p in pressures if p is not None) if has_pressure else [None]

    for i, pressure in enumerate(iter_p):
        subset = df[df[pressure_col] == pressure] if has_pressure else df
        if subset.empty:
            continue

        pivot = (
            subset.pivot_table(index=y_col, columns=x_col, values=carbon_col, aggfunc="mean")
            .sort_index().sort_index(axis=1)
        )
        color_scale = [[0.0, "#dbeeff"], [1.0, PRESSURE_COLORS[i % len(PRESSURE_COLORS)]]]
        label       = f"P = {pressure:g}" if has_pressure else "All data"

        fig.add_trace(go.Surface(
            x=pivot.columns.values, y=pivot.index.values, z=pivot.values,
            name=label, legendgroup=f"s_{i}", showlegend=False,
            opacity=opacity, colorscale=color_scale,
            cmin=0, cmax=carbon_max, showscale=False,
            hovertemplate=(
                f"{x_col}: %{{x:.2f}}<br>{y_col}: %{{y:.2f}}<br>"
                f"{carbon_col}: %{{z:.4f}}<br>"
                + (f"{pressure_col}: {pressure:g}<extra></extra>" if has_pressure else "<extra></extra>")
            ),
        ))
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None], mode="markers",
            name=label, legendgroup=f"s_{i}", showlegend=True,
            marker=dict(size=8, color=PRESSURE_COLORS[i % len(PRESSURE_COLORS)], symbol="square"),
            hoverinfo="skip",
        ))

    fig.update_layout(
        template="plotly_white",
        scene=dict(
            xaxis_title=x_col, yaxis_title=y_col, zaxis_title=carbon_col,
            camera=dict(eye=dict(x=1.3, y=1.6, z=0.54),
                        center=dict(x=0.02, y=0.03, z=-0.2),
                        up=dict(x=0, y=0, z=1)),
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        title=dict(text="Carbon Deposition — 3D Surface", x=0.5, xanchor="center"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.01),
        height=600,
    )
    return fig


def build_zero_plane_figure(df, pressures):
    fig   = go.Figure()
    iter_p = sorted(p for p in pressures if p is not None) if has_pressure else [None]

    for i, pressure in enumerate(iter_p):
        subset = df[df[pressure_col] == pressure].copy() if has_pressure else df.copy()
        if subset.empty:
            continue

        pivot = (
            subset.pivot_table(index=y_col, columns=x_col, values=carbon_col, aggfunc="mean")
            .sort_index().sort_index(axis=1)
        )
        if pivot.empty:
            continue

        color    = PRESSURE_COLORS[i % len(PRESSURE_COLORS)]
        label    = f"P = {pressure:g}" if has_pressure else "All data"
        zero_pts = subset[subset[carbon_col] <= ZERO_TOL]

        if not zero_pts.empty:
            fig.add_trace(go.Scatter(
                x=zero_pts[x_col], y=zero_pts[y_col],
                mode="markers", name=label,
                legendgroup=f"z_{i}", showlegend=True,
                marker=dict(size=8, color=color, opacity=0.25, line=dict(width=1, color=color)),
                hovertemplate=(
                    f"{x_col}: %{{x:.2f}}<br>{y_col}: %{{y:.2f}}<br>"
                    + (f"{pressure_col}: {pressure:g}<br>" if has_pressure else "")
                    + "Carbon ~ 0<extra></extra>"
                ),
            ))

        if pivot.shape[0] > 1 and pivot.shape[1] > 1:
            fig.add_trace(go.Contour(
                x=pivot.columns.values, y=pivot.index.values,
                z=(pivot.values > ZERO_TOL).astype(float),
                name=f"Boundary {label}", legendgroup=f"z_{i}",
                showlegend=False, showscale=False,
                contours=dict(start=0.5, end=0.5, size=1, coloring="none", showlabels=False),
                line=dict(color=color, width=2.5),
                hoverinfo="skip",
            ))

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=45, r=20, t=42, b=45),
        title=dict(text="Carbon = 0 Boundary Plane", x=0.5, xanchor="center"),
        xaxis=dict(title=x_col), yaxis=dict(title=y_col),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.01),
        height=450,
    )
    return fig


def build_species_figure(df, pressures, selected_x_val):
    fig = go.Figure()

    if selected_x_val is None or not has_species:
        fig.update_layout(title="Species flowrates vs Y axis", template="plotly_white", height=480)
        return fig

    ratio_data = df[df[x_col] == selected_x_val].copy()
    iter_p     = sorted(p for p in pressures if p is not None) if has_pressure else [None]

    for i, pressure in enumerate(iter_p):
        subset = (
            ratio_data[ratio_data[pressure_col] == pressure].sort_values(y_col)
            if has_pressure else ratio_data.sort_values(y_col)
        )
        if subset.empty:
            continue

        dash_style = PRESSURE_DASHES[i % len(PRESSURE_DASHES)]
        for j, col in enumerate(species_cols):
            if col not in subset.columns or subset[col].isna().all():
                continue
            color = SPECIES_COLORS[j % len(SPECIES_COLORS)]
            label = f"{col}" + (f" | P={pressure:g}" if has_pressure else "")
            fig.add_trace(go.Scatter(
                x=subset[y_col], y=subset[col],
                mode="lines+markers", name=label,
                legendgroup=f"{col}_p{i}",
                line=dict(color=color, width=2, dash=dash_style),
                marker=dict(size=5, color=color),
                hovertemplate=(
                    f"{y_col}: %{{x:.2f}}<br>{col}: %{{y:.4f}}<br>"
                    + (f"{pressure_col}: {pressure:g}<br>" if has_pressure else "")
                    + f"{x_col}: {selected_x_val:g}<extra></extra>"
                ),
            ))

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=50, r=20, t=44, b=50),
        title=dict(text=f"Species flowrates vs {y_col}  ({x_col} = {selected_x_val:g})", x=0.5, xanchor="center"),
        xaxis=dict(title=y_col), yaxis=dict(title="Flowrate"),
        legend=dict(orientation="v", yanchor="top", y=0.98, xanchor="left", x=1.02),
        height=520,
    )
    return fig


# ── Render charts ──────────────────────────────────────────────────────────────
st.markdown("#### Carbon Deposition Surface")
st.plotly_chart(build_3d_figure(data, selected_pressures, opacity),  use_container_width=True)
st.plotly_chart(build_zero_plane_figure(data, selected_pressures),   use_container_width=True)

if has_species:
    st.divider()
    st.markdown("#### Species Flowrates vs Y Axis")

    sp_c1, sp_c2 = st.columns(2)
    with sp_c1:
        if has_pressure:
            selected_pressures_sp = st.multiselect(
                f"Filter by {pressure_col} — species chart",
                options=available_pressures,
                default=available_pressures,
                format_func=lambda p: f"{p:g}",
            )
            if not selected_pressures_sp:
                selected_pressures_sp = available_pressures
        else:
            selected_pressures_sp = [None]

    with sp_c2:
        default_x      = min(available_x, key=lambda r: abs(r - (sum(available_x) / len(available_x))))
        selected_x_val = st.select_slider(
            f"Select {x_col} value",
            options=available_x,
            value=default_x,
            format_func=lambda r: f"{r:.2f}",
        )

    st.plotly_chart(
        build_species_figure(data, selected_pressures_sp, selected_x_val),
        use_container_width=True,
    )

else:
    st.info("💡 No species columns were mapped — species chart is not available.")

st.divider()
st.caption("Firjan SENAI · Hytron (Neuman-Esser) · USP · Shell")
