"""
charts.py — Geração de gráficos interativos com Plotly.

Função pública:
  generate_charts(df) → lista de dicts com título e dados Plotly em JSON

Gráficos gerados automaticamente conforme o conteúdo do DataFrame:
  1. Histograma de distribuição — um por coluna numérica (máx. 3)
  2. Mapa de correlação (heatmap) — quando há 2 ou mais colunas numéricas
  3. Gráfico de tendência temporal — quando uma coluna de data é detectada
"""

import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


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
        fig = px.histogram(
            df,
            x=col,
            title=f"Distribuição: {col}",
            template="plotly_white",
            color_discrete_sequence=["#6366f1"],  # cor roxa do tema da aplicação
        )
        fig.update_layout(bargap=0.1)
        charts.append({"title": f"Distribuição: {col}", "data": _to_json(fig)})

    # --- Mapa de correlação ---
    # Mostra como as colunas numéricas se relacionam entre si.
    # zmid=0 centraliza a escala de cores em zero (azul = correlação negativa, vermelho = positiva).
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr().round(2)
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.index.tolist(),
                colorscale="RdBu",
                zmid=0,
                text=corr.values.round(2),
                texttemplate="%{text}",
            )
        )
        fig.update_layout(title="Mapa de Correlação", template="plotly_white")
        charts.append({"title": "Mapa de Correlação", "data": _to_json(fig)})

    # --- Gráfico de tendência temporal ---
    # Usa a primeira coluna numérica como eixo Y.
    # O try/except protege contra datas inválidas que não podem ser convertidas.
    if date_col and numeric_cols:
        try:
            df_sorted = df.copy()
            df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")
            df_sorted = df_sorted.dropna(subset=[date_col]).sort_values(date_col)
            target_col = numeric_cols[0]
            fig = px.line(
                df_sorted,
                x=date_col,
                y=target_col,
                title=f"Tendência Temporal: {target_col}",
                template="plotly_white",
                color_discrete_sequence=["#6366f1"],
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
