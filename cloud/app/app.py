from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Poultry Production Monitor",
    page_icon="🥚",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]

DATA_DIR = REPO_ROOT / "data" / "dashboard"
PRODUCTION_FILE = DATA_DIR / "production_dashboard.csv"
ANOMALIES_FILE = DATA_DIR / "df_detected_anomalies.csv"

st.markdown(
    """
    <style>
        .block-container { padding-top: 1.4rem; padding-bottom: 2rem; }
        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            padding: 0.8rem 1rem;
            border-radius: 12px;
        }
        .section-note {
            padding: 0.75rem 1rem;
            border-radius: 10px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 1rem;
        }
        .status-ok {
            padding: 0.75rem 1rem;
            border-radius: 10px;
            background: rgba(40, 167, 69, 0.10);
            border: 1px solid rgba(40, 167, 69, 0.25);
        }
        .status-alert {
            padding: 0.75rem 1rem;
            border-radius: 10px;
            background: rgba(220, 53, 69, 0.10);
            border: 1px solid rgba(220, 53, 69, 0.25);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not PRODUCTION_FILE.exists():
        raise FileNotFoundError(f"No se ha encontrado: {PRODUCTION_FILE}")
    if not ANOMALIES_FILE.exists():
        raise FileNotFoundError(f"No se ha encontrado: {ANOMALIES_FILE}")

    production = pd.read_csv(PRODUCTION_FILE)
    anomalies = pd.read_csv(ANOMALIES_FILE)

    production["capture_date"] = pd.to_datetime(production["capture_date"], errors="coerce")
    anomalies["capture_date"] = pd.to_datetime(anomalies["capture_date"], errors="coerce")

    for col in ["house_number", "battery_number", "level", "position_group"]:
        if col in production.columns:
            production[col] = pd.to_numeric(production[col], errors="coerce").astype("Int64")
        if col in anomalies.columns:
            anomalies[col] = pd.to_numeric(anomalies[col], errors="coerce").astype("Int64")

    return production, anomalies


try:
    production, anomalies = load_data()
except Exception as exc:
    st.error("No se han podido cargar los datos del dashboard.")
    st.code(str(exc))
    st.stop()


BATTERY_KEYS = ["farm_id", "house_number", "battery_number", "capture_date"]


def battery_daily_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "farm_id", "house_number", "battery_number", "capture_date",
        "battery_n_records", "battery_total_egg_count",
        "battery_mean_egg_count", "battery_median_egg_count_daily",
        "battery_mean_confidence", "battery_total_inferences",
        "battery_error_records", "battery_error_rate_pct",
        "temporal_baseline_median", "temporal_deviation_pct",
    ]
    existing = [c for c in cols if c in df.columns]
    return (
        df[existing]
        .drop_duplicates(subset=BATTERY_KEYS)
        .sort_values(BATTERY_KEYS)
        .reset_index(drop=True)
    )


def format_int(value) -> str:
    return "—" if pd.isna(value) else f"{int(round(value)):,}"


def format_pct(value, decimals=1) -> str:
    return "—" if pd.isna(value) else f"{value:.{decimals}f}%"


def format_float(value, decimals=3) -> str:
    return "—" if pd.isna(value) else f"{value:.{decimals}f}"


def temporal_anomalies_for_selection(farm_id, selected_date, house_number=None):
    df = anomalies[
        (anomalies["anomaly_type"] == "TEMPORAL")
        & (anomalies["farm_id"] == farm_id)
        & (anomalies["capture_date"] == selected_date)
    ].copy()
    if house_number is not None:
        df = df[df["house_number"] == house_number]
    return df


def spatial_anomalies_for_selection(farm_id, house_number=None):
    df = anomalies[
        (anomalies["anomaly_type"] == "SPATIAL")
        & (anomalies["farm_id"] == farm_id)
    ].copy()
    if house_number is not None:
        df = df[df["house_number"] == house_number]
    return df


st.title("🥚 Poultry Production Monitor")
st.caption("Seguimiento diario de producción y detección de anomalías")

# Navegación segura entre vistas.
# Los botones no modifican directamente el estado del radio una vez creado.
if "page_selector" not in st.session_state:
    st.session_state["page_selector"] = "Producción"

# Si en el ciclo anterior se solicitó un cambio de vista, se aplica
# ANTES de instanciar el widget del menú lateral.
if "navigate_to" in st.session_state:
    st.session_state["page_selector"] = st.session_state.pop("navigate_to")

page = st.sidebar.radio(
    "Vista",
    ["Producción", "Anomalías"],
    key="page_selector",
)
st.sidebar.divider()


if page == "Producción":
    st.subheader("Producción diaria")

    farms = sorted(production["farm_id"].dropna().unique().tolist())
    selected_farm = st.sidebar.selectbox("Granja", farms)

    farm_data = production[production["farm_id"] == selected_farm].copy()

    house_options_sidebar = sorted(
        farm_data["house_number"].dropna().unique().tolist()
    )
    selected_house_sidebar = st.sidebar.selectbox(
        "Nave",
        ["Todas"] + house_options_sidebar,
    )

    if selected_house_sidebar == "Todas":
        scope_data = farm_data.copy()
        selected_house_value = None
    else:
        selected_house_value = selected_house_sidebar
        scope_data = farm_data[
            farm_data["house_number"] == selected_house_value
        ].copy()

    available_dates = sorted(
        scope_data["capture_date"].dropna().dt.date.unique().tolist()
    )

    if not available_dates:
        st.warning("No hay fechas disponibles para esta selección.")
        st.stop()

    selected_date_value = st.sidebar.date_input(
        "Fecha",
        value=max(available_dates),
        min_value=min(available_dates),
        max_value=max(available_dates),
    )

    if selected_date_value not in available_dates:
        st.warning("No hay datos para la fecha seleccionada.")
        st.stop()

    selected_date = pd.Timestamp(selected_date_value)

    selected = scope_data[
        scope_data["capture_date"] == selected_date
    ].copy()

    battery_day = battery_daily_table(selected)

    temporal_today = temporal_anomalies_for_selection(
        selected_farm,
        selected_date,
        selected_house_value,
    )
    spatial_scope = spatial_anomalies_for_selection(
        selected_farm,
        selected_house_value,
    )

    if temporal_today.empty and spatial_scope.empty:
        st.markdown(
            '<div class="status-ok"><b>Estado:</b> no se han detectado anomalías para esta selección.</div>',
            unsafe_allow_html=True,
        )
    else:
        total_selection_alerts = len(temporal_today) + len(spatial_scope)

        st.markdown(
            f'<div class="status-alert"><b>Atención:</b> '
            f'{total_selection_alerts} anomalía(s) detectada(s) para esta selección.</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Ver anomalías detectadas", expanded=True):
            if not temporal_today.empty:
                st.markdown("**Anomalías temporales**")

                for i, row in temporal_today.reset_index(drop=True).iterrows():
                    c_info, c_button = st.columns([5, 1])

                    c_info.write(
                        f"Nave {int(row['house_number'])} · "
                        f"Batería {int(row['battery_number'])} · "
                        f"{row['capture_date'].strftime('%d/%m/%Y')} · "
                        f"Desviación {row['deviation_pct']:.2f}%"
                    )

                    if c_button.button(
                        "Ver",
                        key=f"open_temporal_{i}_{selected_farm}_{selected_date.date()}",
                        use_container_width=True,
                    ):
                        st.session_state["pending_anomaly"] = {
                            "farm_id": row["farm_id"],
                            "anomaly_type": "TEMPORAL",
                            "house_number": int(row["house_number"]),
                            "battery_number": int(row["battery_number"]),
                            "capture_date": row["capture_date"].date(),
                        }
                        st.session_state["navigate_to"] = "Anomalías"
                        st.rerun()

            if not spatial_scope.empty:
                st.markdown("**Anomalías espaciales persistentes**")

                for i, row in spatial_scope.reset_index(drop=True).iterrows():
                    c_info, c_button = st.columns([5, 1])

                    cage_min = int(row["cage_id_min"]) if pd.notna(row.get("cage_id_min")) else None
                    cage_max = int(row["cage_id_max"]) if pd.notna(row.get("cage_id_max")) else None
                    cage_text = (
                        f"Jaulas {cage_min}–{cage_max}"
                        if cage_min is not None and cage_max is not None
                        else f"Posición {int(row['position_group'])}–{int(row['position_group']) + 49}"
                    )

                    c_info.write(
                        f"Nave {int(row['house_number'])} · "
                        f"Batería {int(row['battery_number'])} · "
                        f"Nivel {int(row['level'])} · "
                        f"{row['side']} · "
                        f"{cage_text}"
                    )

                    if c_button.button(
                        "Ver",
                        key=f"open_spatial_{i}_{selected_farm}",
                        use_container_width=True,
                    ):
                        st.session_state["pending_anomaly"] = {
                            "farm_id": row["farm_id"],
                            "anomaly_type": "SPATIAL",
                            "house_number": int(row["house_number"]),
                            "battery_number": int(row["battery_number"]),
                            "level": int(row["level"]),
                            "side": row["side"],
                            "position_group": int(row["position_group"]),
                            "cage_id_min": int(row["cage_id_min"]) if pd.notna(row.get("cage_id_min")) else None,
                            "cage_id_max": int(row["cage_id_max"]) if pd.notna(row.get("cage_id_max")) else None,
                        }
                        st.session_state["navigate_to"] = "Anomalías"
                        st.rerun()

    st.write("")

    total_eggs = battery_day["battery_total_egg_count"].sum()
    total_records = battery_day["battery_n_records"].sum()
    weighted_mean = total_eggs / total_records if total_records > 0 else float("nan")

    total_inferences = battery_day["battery_total_inferences"].sum()
    total_errors = battery_day["battery_error_records"].sum()
    error_rate = 100 * total_errors / total_inferences if total_inferences > 0 else float("nan")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de huevos detectados", format_int(total_eggs))
    c2.metric("Media de huevos / jaula", format_float(weighted_mean, 3))
    c3.metric("Tasa de errores de inferencia", format_pct(error_rate, 2))

    st.divider()
    st.markdown("### Producción por batería")

    plot_df = battery_day.copy()
    plot_df["battery_label"] = (
        "Nave " + plot_df["house_number"].astype(str)
        + " · Batería " + plot_df["battery_number"].astype(str)
    )

    fig = px.bar(
        plot_df,
        x="battery_label",
        y="battery_mean_egg_count",
        hover_data={
            "battery_total_egg_count": ":,.0f",
            "battery_error_rate_pct": ":.2f",
            "battery_label": False,
        },
        labels={
            "battery_label": "",
            "battery_mean_egg_count": "Media de huevos / jaula",
            "battery_total_egg_count": "Total de huevos",
            "battery_error_rate_pct": "Tasa de error (%)",
        },
    )
    fig.update_layout(height=430, xaxis_tickangle=-35, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("### Evolución de la producción")

    house_options = sorted(scope_data["house_number"].dropna().unique().tolist())
    col_a, col_b = st.columns(2)

    selected_house = col_a.selectbox(
        "Nave",
        house_options,
        key="prod_house",
        disabled=(selected_house_sidebar != "Todas"),
    )

    battery_options = sorted(
        scope_data[
            scope_data["house_number"] == selected_house
        ]["battery_number"].dropna().unique().tolist()
    )

    selected_battery = col_b.selectbox("Batería", battery_options, key="prod_battery")

    history_source = battery_daily_table(scope_data)
    history = history_source[
        (history_source["house_number"] == selected_house)
        & (history_source["battery_number"] == selected_battery)
    ].sort_values("capture_date")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history["capture_date"],
            y=history["battery_mean_egg_count"],
            mode="lines+markers",
            name="Producción media",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=history["capture_date"],
            y=history["temporal_baseline_median"],
            mode="lines",
            name="Baseline histórico",
            line=dict(dash="dash"),
        )
    )

    matching_temporal = anomalies[
        (anomalies["anomaly_type"] == "TEMPORAL")
        & (anomalies["farm_id"] == selected_farm)
        & (anomalies["house_number"] == selected_house)
        & (anomalies["battery_number"] == selected_battery)
    ].copy()

    if not matching_temporal.empty:
        fig.add_trace(
            go.Scatter(
                x=matching_temporal["capture_date"],
                y=matching_temporal["mean_egg_count"],
                mode="markers",
                name="Anomalía detectada",
                marker=dict(size=14, symbol="x"),
            )
        )

    fig.update_xaxes(
        tickmode="array",
        tickvals=history["capture_date"],
        ticktext=[d.strftime("%d %b") for d in history["capture_date"]],
    )

    fig.update_yaxes(
        range=[0, 1.2],
        dtick=0.2,
    )

    fig.update_layout(
        height=430,
        xaxis_title="Fecha",
        yaxis_title="Media de huevos / jaula",
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("### Distribución espacial de la producción")
    st.caption(
        "Permite revisar si existen zonas concretas dentro de la batería "
        "con una producción inferior al resto."
    )

    spatial_day = selected[
        (selected["house_number"] == selected_house)
        & (selected["battery_number"] == selected_battery)
    ].copy()

    side_options = sorted(spatial_day["side"].dropna().unique().tolist())
    selected_side = st.selectbox("Lado", side_options, key="prod_side")

    heat_df = spatial_day[spatial_day["side"] == selected_side].copy()

    if heat_df.empty:
        st.info("No hay datos espaciales disponibles para esta selección.")
    else:
        heat_pivot = heat_df.pivot_table(
            index="level",
            columns="position_group",
            values="mean_egg_count",
            aggfunc="mean",
        ).sort_index()

        position_limits = [int(c) + 49 for c in heat_pivot.columns]
        levels = [int(v) for v in heat_pivot.index]

        hover_matrix = []
        for level in heat_pivot.index:
            row_hover = []
            for position_group in heat_pivot.columns:
                cell = heat_df[
                    (heat_df["level"] == level)
                    & (heat_df["position_group"] == position_group)
                ]
                if not cell.empty:
                    cage_min = int(cell["cage_id_min"].min())
                    cage_max = int(cell["cage_id_max"].max())
                    row_hover.append(f"{cage_min}–{cage_max}")
                else:
                    row_hover.append("-")
            hover_matrix.append(row_hover)

        fig = go.Figure(
            data=go.Heatmap(
                z=heat_pivot.to_numpy(),
                x=position_limits,
                y=levels,
                text=heat_pivot.to_numpy(),
                customdata=hover_matrix,
                texttemplate="%{text:.2f}",
                colorbar=dict(title="Media huevos / jaula"),
                hovertemplate=(
                    "Posición: %{x}<br>"
                    "Nivel: %{y}<br>"
                    "Jaulas: %{customdata}<br>"
                    "Media huevos/jaula: %{z:.2f}"
                    "<extra></extra>"
                ),
            )
        )

        fig.update_xaxes(
            title="Posición",
            tickmode="array",
            tickvals=position_limits,
            ticktext=[str(v) for v in position_limits],
        )

        # Eje físico de la batería: nivel 1 abajo y nivel más alto arriba.
        fig.update_yaxes(
            title="Nivel",
            tickmode="array",
            tickvals=levels,
            ticktext=[str(v) for v in levels],
            range=[min(levels) - 0.5, max(levels) + 0.5],
            dtick=1,
        )

        fig.update_layout(
            height=320,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


else:
    st.subheader("Anomalías detectadas")

    total_anomalies = len(anomalies)
    temporal_count = int((anomalies["anomaly_type"] == "TEMPORAL").sum())
    spatial_count = int((anomalies["anomaly_type"] == "SPATIAL").sum())
    affected_farms = anomalies["farm_id"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de alertas", total_anomalies)
    c2.metric("Temporales", temporal_count)
    c3.metric("Espaciales", spatial_count)
    c4.metric("Granjas afectadas", affected_farms)

    st.divider()

    pending = st.session_state.pop("pending_anomaly", None)

    anomaly_farms = sorted(anomalies["farm_id"].dropna().unique().tolist())
    farm_options = ["Todas"] + anomaly_farms

    default_farm = pending["farm_id"] if pending else "Todas"
    selected_anomaly_farm = st.sidebar.selectbox(
        "Granja",
        farm_options,
        index=farm_options.index(default_farm) if default_farm in farm_options else 0,
    )

    type_options = ["Todas", "TEMPORAL", "SPATIAL"]
    default_type = pending["anomaly_type"] if pending else "Todas"
    selected_type = st.sidebar.selectbox(
        "Tipo de anomalía",
        type_options,
        index=type_options.index(default_type) if default_type in type_options else 0,
    )

    filtered = anomalies.copy()

    if selected_anomaly_farm != "Todas":
        filtered = filtered[filtered["farm_id"] == selected_anomaly_farm]

    if selected_type != "Todas":
        filtered = filtered[filtered["anomaly_type"] == selected_type]

    available_houses = sorted(
        filtered["house_number"].dropna().astype(int).unique().tolist()
    )
    house_filter_options = ["Todas"] + available_houses
    default_house = pending.get("house_number") if pending else "Todas"

    selected_anomaly_house = st.sidebar.selectbox(
        "Nave",
        house_filter_options,
        index=(
            house_filter_options.index(default_house)
            if default_house in house_filter_options
            else 0
        ),
    )

    if selected_anomaly_house != "Todas":
        filtered = filtered[
            filtered["house_number"] == selected_anomaly_house
        ]

    available_batteries = sorted(
        filtered["battery_number"].dropna().astype(int).unique().tolist()
    )
    battery_filter_options = ["Todas"] + available_batteries
    default_battery = pending.get("battery_number") if pending else "Todas"

    selected_anomaly_battery = st.sidebar.selectbox(
        "Batería",
        battery_filter_options,
        index=(
            battery_filter_options.index(default_battery)
            if default_battery in battery_filter_options
            else 0
        ),
    )

    if selected_anomaly_battery != "Todas":
        filtered = filtered[
            filtered["battery_number"] == selected_anomaly_battery
        ]

    if pending and pending.get("capture_date") is not None:
        pending_date = pd.Timestamp(pending["capture_date"])
        if selected_type == "TEMPORAL":
            filtered = filtered[
                filtered["capture_date"] == pending_date
            ]

    if pending:
        st.info(
            "Mostrando la anomalía seleccionada desde la vista de Producción."
        )

        if pending.get("anomaly_type") == "SPATIAL":
            cage_min = pending.get("cage_id_min")
            cage_max = pending.get("cage_id_max")
            if cage_min is not None and cage_max is not None:
                st.markdown(f"**Jaulas afectadas:** {cage_min}–{cage_max}")

    temporal = filtered[filtered["anomaly_type"] == "TEMPORAL"].copy()

    st.markdown("### Anomalías temporales")
    if temporal.empty:
        st.success("No hay anomalías temporales para los filtros seleccionados.")
    else:
        temporal["location"] = (
            temporal["farm_id"].astype(str)
            + " · N" + temporal["house_number"].astype(str)
            + " · B" + temporal["battery_number"].astype(str)
        )

        fig = px.bar(
            temporal.sort_values("deviation_pct"),
            x="deviation_pct",
            y="location",
            orientation="h",
            labels={
                "deviation_pct": "Desviación respecto al baseline (%)",
                "location": "",
            },
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.dataframe(
            temporal[
                [
                    "farm_id", "house_number", "battery_number",
                    "capture_date", "mean_egg_count",
                    "baseline_median", "deviation_pct",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    spatial = filtered[filtered["anomaly_type"] == "SPATIAL"].copy()

    st.markdown("### Anomalías espaciales")

    if spatial.empty:
        st.success("No hay anomalías espaciales para los filtros seleccionados.")
    else:
        spatial_table = spatial[
            [
                "farm_id",
                "house_number",
                "battery_number",
                "level",
                "side",
                "cage_id_min",
                "cage_id_max",
            ]
        ].copy()

        spatial_table["Jaulas afectadas"] = spatial_table.apply(
            lambda row: (
                f"{int(row['cage_id_min'])}–{int(row['cage_id_max'])}"
                if pd.notna(row["cage_id_min"]) and pd.notna(row["cage_id_max"])
                else "-"
            ),
            axis=1,
        )

        spatial_table = spatial_table[
            [
                "farm_id",
                "house_number",
                "battery_number",
                "level",
                "side",
                "Jaulas afectadas",
            ]
        ]

        spatial_table.columns = [
            "Granja",
            "Nave",
            "Batería",
            "Nivel",
            "Lado",
            "Jaulas afectadas",
        ]

        st.dataframe(
            spatial_table,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Revisar batería afectada")

        inspect_farm_options = sorted(spatial["farm_id"].unique())
        inspect_default_farm = (
            pending.get("farm_id")
            if pending and pending.get("anomaly_type") == "SPATIAL"
            else inspect_farm_options[0]
        )

        anomaly_farm = st.selectbox(
            "Granja a revisar",
            inspect_farm_options,
            index=(
                inspect_farm_options.index(inspect_default_farm)
                if inspect_default_farm in inspect_farm_options
                else 0
            ),
            key="spatial_inspect_farm",
        )

        farm_spatial = spatial[spatial["farm_id"] == anomaly_farm]

        house_battery_options = (
            farm_spatial[["house_number", "battery_number"]]
            .drop_duplicates()
            .sort_values(["house_number", "battery_number"])
        )

        hb_labels = [
            (int(r.house_number), int(r.battery_number))
            for r in house_battery_options.itertuples()
        ]

        default_hb = (
            (
                pending.get("house_number"),
                pending.get("battery_number"),
            )
            if pending and pending.get("anomaly_type") == "SPATIAL"
            else hb_labels[0]
        )

        inspect_house, inspect_battery = st.selectbox(
            "Nave / Batería",
            hb_labels,
            index=hb_labels.index(default_hb) if default_hb in hb_labels else 0,
            format_func=lambda x: f"Nave {x[0]} · Batería {x[1]}",
            key="spatial_inspect_hb",
        )

        available_prod = production[
            (production["farm_id"] == anomaly_farm)
            & (production["house_number"] == inspect_house)
            & (production["battery_number"] == inspect_battery)
        ].copy()

        inspect_dates = sorted(
            available_prod["capture_date"].dropna().dt.date.unique().tolist()
        )

        inspect_date_value = st.date_input(
            "Fecha a revisar",
            value=max(inspect_dates),
            min_value=min(inspect_dates),
            max_value=max(inspect_dates),
            key="spatial_inspect_date",
        )

        inspect_date = pd.Timestamp(inspect_date_value)

        inspect_day = available_prod[
            available_prod["capture_date"] == inspect_date
        ].copy()

        inspect_sides = sorted(inspect_day["side"].dropna().unique().tolist())

        default_side = (
            pending.get("side")
            if pending and pending.get("anomaly_type") == "SPATIAL"
            else inspect_sides[0]
        )

        inspect_side = st.selectbox(
            "Lado",
            inspect_sides,
            index=inspect_sides.index(default_side) if default_side in inspect_sides else 0,
            key="spatial_inspect_side",
        )

        # ----------------------------------------------------
        # Select the exact spatial anomaly within the battery.
        # ----------------------------------------------------
        spatial_candidates = spatial[
            (spatial["farm_id"] == anomaly_farm)
            & (spatial["house_number"] == inspect_house)
            & (spatial["battery_number"] == inspect_battery)
            & (spatial["side"] == inspect_side)
        ].copy()

        if not spatial_candidates.empty:
            spatial_candidates = spatial_candidates.sort_values(
                ["level", "position_group"]
            ).reset_index(drop=True)

            candidate_options = list(range(len(spatial_candidates)))

            default_candidate_index = 0
            if pending and pending.get("anomaly_type") == "SPATIAL":
                pending_level = pending.get("level")
                pending_group = pending.get("position_group")

                matches = spatial_candidates[
                    (spatial_candidates["level"] == pending_level)
                    & (spatial_candidates["position_group"] == pending_group)
                ]

                if not matches.empty:
                    default_candidate_index = int(matches.index[0])

            selected_candidate_index = st.selectbox(
                "Zona anómala",
                candidate_options,
                index=default_candidate_index,
                format_func=lambda i: (
                    f"Nivel {int(spatial_candidates.loc[i, 'level'])} · "
                    f"Jaulas "
                    f"{int(spatial_candidates.loc[i, 'cage_id_min'])}–"
                    f"{int(spatial_candidates.loc[i, 'cage_id_max'])}"
                ),
                key="spatial_anomaly_zone",
            )

            selected_spatial_anomaly = spatial_candidates.loc[
                selected_candidate_index
            ]

            selected_level = int(selected_spatial_anomaly["level"])
            selected_position_group = int(
                selected_spatial_anomaly["position_group"]
            )
            selected_cage_min = int(
                selected_spatial_anomaly["cage_id_min"]
            )
            selected_cage_max = int(
                selected_spatial_anomaly["cage_id_max"]
            )

            # ------------------------------------------------
            # Historical evolution of the affected cage group.
            # ------------------------------------------------
            history = available_prod[
                (available_prod["side"] == inspect_side)
                & (available_prod["level"] == selected_level)
                & (
                    available_prod["position_group"]
                    == selected_position_group
                )
            ].copy()

            history = history.sort_values("capture_date")

            if not history.empty:
                # Same spatial criteria used by the anomaly analysis.
                spatial_dev_threshold = -8.06
                zero_rate_threshold = 18.0

                history["is_spatial_anomaly"] = (
                    (
                        history["spatial_deviation_pct"]
                        < spatial_dev_threshold
                    )
                    & (
                        history["zero_egg_rate_pct"]
                        > zero_rate_threshold
                    )
                )

                anomaly_days = history[
                    history["is_spatial_anomaly"]
                ]

                st.markdown("#### Evolución histórica de la zona afectada")

                if not anomaly_days.empty:
                    first_anomaly_date = anomaly_days[
                        "capture_date"
                    ].min()

                    st.caption(
                        f"Jaulas {selected_cage_min}–{selected_cage_max} · "
                        f"Nivel {selected_level} · {inspect_side} · "
                        f"Anomalía observada desde "
                        f"{first_anomaly_date.strftime('%d/%m/%Y')}"
                    )
                else:
                    st.caption(
                        f"Jaulas {selected_cage_min}–{selected_cage_max} · "
                        f"Nivel {selected_level} · {inspect_side}"
                    )

                history_fig = go.Figure()

                history_fig.add_trace(
                    go.Scatter(
                        x=history["capture_date"],
                        y=history["mean_egg_count"],
                        mode="lines+markers",
                        name="Jaulas afectadas",
                        hovertemplate=(
                            "Fecha: %{x|%d/%m/%Y}<br>"
                            "Media huevos/jaula: %{y:.2f}"
                            "<extra></extra>"
                        ),
                    )
                )

                history_fig.add_trace(
                    go.Scatter(
                        x=history["capture_date"],
                        y=history["battery_median_egg_count"],
                        mode="lines+markers",
                        name="Referencia batería",
                        hovertemplate=(
                            "Fecha: %{x|%d/%m/%Y}<br>"
                            "Mediana batería: %{y:.2f}"
                            "<extra></extra>"
                        ),
                    )
                )

                if not anomaly_days.empty:
                    history_fig.add_trace(
                        go.Scatter(
                            x=anomaly_days["capture_date"],
                            y=anomaly_days["mean_egg_count"],
                            mode="markers",
                            name="Día con anomalía",
                            marker=dict(size=11, symbol="circle-open"),
                            hovertemplate=(
                                "Fecha: %{x|%d/%m/%Y}<br>"
                                "Anomalía espacial<br>"
                                "Media huevos/jaula: %{y:.2f}"
                                "<extra></extra>"
                            ),
                        )
                    )

                history_fig.update_yaxes(
                    title="Media huevos / jaula",
                    range=[0, 1.2],
                    dtick=0.2,
                )

                history_fig.update_xaxes(
                    title="Fecha",
                    tickmode="array",
                    tickvals=history["capture_date"],
                    ticktext=[
                        d.strftime("%d %b")
                        for d in history["capture_date"]
                    ],
                )

                history_fig.update_layout(
                    height=360,
                    margin=dict(l=20, r=20, t=20, b=20),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="left",
                        x=0,
                    ),
                )

                st.plotly_chart(
                    history_fig,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

        inspect_heat = inspect_day[inspect_day["side"] == inspect_side]

        heat_pivot = inspect_heat.pivot_table(
            index="level",
            columns="position_group",
            values="mean_egg_count",
            aggfunc="mean",
        ).sort_index()

        position_limits = [int(c) + 49 for c in heat_pivot.columns]
        levels = [int(v) for v in heat_pivot.index]

        hover_matrix = []
        for level in heat_pivot.index:
            row_hover = []
            for position_group in heat_pivot.columns:
                cell = inspect_heat[
                    (inspect_heat["level"] == level)
                    & (inspect_heat["position_group"] == position_group)
                ]
                if not cell.empty:
                    cage_min = int(cell["cage_id_min"].min())
                    cage_max = int(cell["cage_id_max"].max())
                    row_hover.append(f"{cage_min}–{cage_max}")
                else:
                    row_hover.append("-")
            hover_matrix.append(row_hover)

        fig = go.Figure(
            data=go.Heatmap(
                z=heat_pivot.to_numpy(),
                x=position_limits,
                y=levels,
                text=heat_pivot.to_numpy(),
                customdata=hover_matrix,
                texttemplate="%{text:.2f}",
                colorbar=dict(title="Media huevos / jaula"),
                hovertemplate=(
                    "Posición: %{x}<br>"
                    "Nivel: %{y}<br>"
                    "Jaulas: %{customdata}<br>"
                    "Media huevos/jaula: %{z:.2f}"
                    "<extra></extra>"
                ),
            )
        )

        fig.update_xaxes(
            title="Posición",
            tickmode="array",
            tickvals=position_limits,
            ticktext=[str(v) for v in position_limits],
        )

        # Nivel 1 abajo; niveles superiores físicamente arriba.
        fig.update_yaxes(
            title="Nivel",
            tickmode="array",
            tickvals=levels,
            ticktext=[str(v) for v in levels],
            range=[min(levels) - 0.5, max(levels) + 0.5],
            dtick=1,
        )

        matching_positions = spatial[
            (spatial["farm_id"] == anomaly_farm)
            & (spatial["house_number"] == inspect_house)
            & (spatial["battery_number"] == inspect_battery)
            & (spatial["side"] == inspect_side)
        ]

        if not matching_positions.empty:
            for row in matching_positions.itertuples():
                position_limit = int(row.position_group) + 49

                fig.add_shape(
                    type="rect",
                    x0=position_limit - 25,
                    x1=position_limit + 25,
                    y0=int(row.level) - 0.5,
                    y1=int(row.level) + 0.5,
                    line=dict(width=4),
                )

        fig.update_layout(
            height=340,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
