"""
charts.py — Geração de gráficos interativos com Plotly.

Função pública:
  generate_charts(df) → lista de dicts com título e dados Plotly em JSON

Gráficos gerados automaticamente conforme o conteúdo do DataFrame:
  1. Histograma de distribuição — um por coluna numérica (máx. 3)
  2. Top categorias — uma barra horizontal por coluna categórica relevante (máx. 2)
  3. Mapa de correlação (heatmap) — quando há 2 ou mais colunas numéricas
  4. Gráfico de tendência temporal — quando uma coluna de data é detectada
"""

import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta consistente com o tema da aplicação (--primary: #6366f1)
PRIMARY      = "#6366f1"
PRIMARY_SOFT = "#a5b4fc"

# Layout-base aplicado a todos os gráficos. O título é deixado em branco
# porque o card já tem um <h4> com o nome — manter o título interno do
# Plotly causava sobreposição visual com o cabeçalho do card.
BASE_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=12, color="#475569"),
    margin=dict(t=20, r=20, b=50, l=60),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    hoverlabel=dict(font_family="Inter, Segoe UI, system-ui, sans-serif"),
    xaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0", zerolinecolor="#e2e8f0"),
    yaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0", zerolinecolor="#e2e8f0"),
)


def generate_charts(df: pd.DataFrame) -> list[dict]:
    """
    Analisa o DataFrame e produz uma lista de gráficos Plotly.
    Cada item da lista é um dict com 'title' e 'data' (JSON do Plotly).
    O frontend usa Plotly.newPlot() para renderizar os gráficos diretamente.
    """
    charts = []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    date_col = _detect_date_column(df)

    # --- Histogramas (distribuição de valores) ---
    # Limitado a 3 colunas para não sobrecarregar a tela
    for col in numeric_cols[:3]:
        series = df[col].dropna()
        if series.empty:
            continue
        fig = px.histogram(
            df,
            x=col,
            nbins=30,
            color_discrete_sequence=[PRIMARY],
        )
        fig.update_traces(marker_line_color="white", marker_line_width=1)
        fig.update_layout(
            **BASE_LAYOUT,
            bargap=0.08,
            xaxis_title=col,
            yaxis_title="Frequência",
        )
        charts.append({"title": f"Distribuição: {col}", "data": _to_json(fig)})

    # --- Top categorias (barra horizontal) ---
    # Mostra os 10 valores mais frequentes das colunas categóricas relevantes.
    # Ignora colunas com cardinalidade extrema (IDs únicos ou constantes).
    cat_cols = [
        c for c in df.select_dtypes(include=["object", "category"]).columns
        if 2 <= df[c].nunique(dropna=True) <= 500 and c != date_col
    ][:2]
    for col in cat_cols:
        top = df[col].dropna().astype(str).value_counts().head(10).iloc[::-1]
        if top.empty:
            continue
        fig = go.Figure(
            go.Bar(
                x=top.values,
                y=top.index,
                orientation="h",
                marker=dict(color=PRIMARY),
                hovertemplate="<b>%{y}</b><br>%{x} ocorrências<extra></extra>",
            )
        )
        fig.update_layout(
            **{**BASE_LAYOUT, "margin": dict(t=20, r=20, b=50, l=140)},
            xaxis_title="Ocorrências",
            yaxis_title=None,
        )
        charts.append({"title": f"Top 10: {col}", "data": _to_json(fig)})

    # --- Mapa de correlação ---
    # Mostra como as colunas numéricas se relacionam entre si.
    # zmid=0 centraliza a escala de cores em zero (azul = correlação negativa, vermelho = positiva).
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr().round(2)
        # Esconde os números quando há muitas colunas (ficariam ilegíveis).
        show_text = len(numeric_cols) <= 8
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.index.tolist(),
                colorscale="RdBu",
                zmid=0,
                zmin=-1,
                zmax=1,
                text=corr.values if show_text else None,
                texttemplate="%{text:.2f}" if show_text else None,
                textfont=dict(size=11),
                hovertemplate="%{y} × %{x}<br>Correlação: %{z:.2f}<extra></extra>",
                colorbar=dict(thickness=12, len=0.8, outlinewidth=0),
            )
        )
        heatmap_layout = {
            **BASE_LAYOUT,
            "margin": dict(t=20, r=20, b=90, l=120),
            "xaxis": {**BASE_LAYOUT["xaxis"], "tickangle": -35, "automargin": True},
            "yaxis": {**BASE_LAYOUT["yaxis"], "automargin": True},
        }
        fig.update_layout(**heatmap_layout)
        charts.append({"title": "Mapa de Correlação", "data": _to_json(fig)})

    # --- Gráfico de tendência temporal ---
    # Usa a primeira coluna numérica como eixo Y.
    # Quando há muitos pontos, agrega por dia para reduzir ruído visual.
    # O try/except protege contra datas inválidas que não podem ser convertidas.
    if date_col and numeric_cols:
        try:
            df_sorted = df[[date_col, numeric_cols[0]]].copy()
            df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")
            df_sorted = df_sorted.dropna().sort_values(date_col)
            target_col = numeric_cols[0]

            if len(df_sorted) > 200:
                df_sorted = (
                    df_sorted.groupby(df_sorted[date_col].dt.date)[target_col]
                    .sum()
                    .reset_index()
                )
                df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])

            fig = go.Figure(
                go.Scatter(
                    x=df_sorted[date_col],
                    y=df_sorted[target_col],
                    mode="lines+markers",
                    line=dict(color=PRIMARY, width=2),
                    marker=dict(color=PRIMARY, size=5),
                    fill="tozeroy",
                    fillcolor="rgba(99,102,241,0.08)",
                    hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.2f}<extra></extra>",
                )
            )
            fig.update_layout(
                **BASE_LAYOUT,
                xaxis_title=date_col,
                yaxis_title=target_col,
            )
            charts.append({"title": f"Tendência Temporal: {target_col}", "data": _to_json(fig)})
        except Exception:
            pass  # coluna de data inválida: ignora o gráfico temporal silenciosamente

    return charts


def _detect_date_column(df: pd.DataFrame) -> str | None:
    """
    Tenta identificar uma coluna de data no DataFrame.
    Verifica primeiro o dtype do Pandas; se não encontrar, procura
    por palavras-chave comuns no nome da coluna (data, date, dt_, ano, mes...).
    Retorna o nome da primeira coluna encontrada ou None.
    """
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
        lower = col.lower()
        if any(k in lower for k in ("data", "date", "dt_", "ano", "year", "mes", "month")):
            return col
    return None


def _to_json(fig) -> dict:
    """
    Converte uma figura Plotly para um dicionário Python puro (sem tipos numpy),
    passando pela serialização JSON intermediária do Plotly.
    Isso garante que o resultado seja serializável pelo FastAPI.
    """
    return json.loads(fig.to_json())
