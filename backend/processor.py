"""
processor.py — Leitura e processamento de arquivos com Pandas e extratores de texto.

Formatos suportados:
  - CSV, XLSX, XLS  → tabela (DataFrame)
  - PDF             → tabela se houver tabelas; senão texto
  - HTML / HTM      → tabela se houver <table>; senão texto extraído
  - TXT             → tabela se for CSV-like (com separador); senão texto

Funções públicas:
  read_file(path)          → dict {kind, df, text, file_type}
  get_summary(df)          → resumo estatístico para tabelas (DataFrame)
  get_text_summary(...)    → resumo para arquivos de texto puro
"""

from io import StringIO
from pathlib import Path

import pandas as pd


def read_file(path: str) -> dict:
    """
    Lê o arquivo e retorna um dicionário com os dados extraídos:
      {
        "kind":      "table" | "text",
        "df":        DataFrame ou None,
        "text":      str ou None,
        "file_type": descrição do formato detectado
      }
    """
    ext = Path(path).suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(path, encoding="utf-8", on_bad_lines="skip")
        return {"kind": "table", "df": df, "text": None, "file_type": "CSV"}

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
        return {"kind": "table", "df": df, "text": None, "file_type": "Excel"}

    if ext == ".pdf":
        return _read_pdf(path)

    if ext in (".html", ".htm"):
        return _read_html(path)

    if ext == ".txt":
        return _read_txt(path)

    raise ValueError(f"Formato não suportado: {ext}")


def _read_pdf(path: str) -> dict:
    """
    Extrai conteúdo de um PDF. Se houver tabelas, usa a maior como DataFrame;
    caso contrário, retorna todo o texto extraído das páginas.
    """
    import pdfplumber

    text_parts = []
    tables = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
            for tbl in page.extract_tables():
                # Considera apenas tabelas com pelo menos cabeçalho + 1 linha
                if tbl and len(tbl) >= 2 and any(tbl[0]):
                    tables.append(tbl)

    if tables:
        # Usa a maior tabela encontrada (mais linhas)
        largest = max(tables, key=len)
        headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(largest[0])]
        rows = [list(r) for r in largest[1:]]
        df = pd.DataFrame(rows, columns=headers)
        # Tenta converter colunas numéricas que vieram como string do PDF
        for col in df.columns:
            converted = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            if converted.notna().sum() / max(len(df), 1) > 0.7:
                df[col] = converted
        return {"kind": "table", "df": df, "text": None,
                "file_type": f"PDF ({len(tables)} tabela(s) detectada(s))"}

    return {"kind": "text", "df": None, "text": "\n\n".join(text_parts), "file_type": "PDF"}


def _read_html(path: str) -> dict:
    """
    Extrai conteúdo de um HTML. Se houver <table>, usa a maior como DataFrame;
    caso contrário, retorna o texto limpo (sem <script>/<style>/tags).
    """
    # Tenta extrair tabelas primeiro
    try:
        tables = pd.read_html(path, encoding="utf-8")
        if tables:
            largest = max(tables, key=len)
            return {"kind": "table", "df": largest, "text": None,
                    "file_type": f"HTML ({len(tables)} tabela(s) detectada(s))"}
    except (ValueError, ImportError):
        pass  # nenhuma tabela encontrada — segue para extração de texto

    from bs4 import BeautifulSoup
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return {"kind": "text", "df": None, "text": text, "file_type": "HTML"}


def _read_txt(path: str) -> dict:
    """
    Lê um TXT. Detecta se há um separador comum (',', ';', tab, '|')
    e tenta tratar como tabela; se não houver estrutura, retorna texto puro.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Tenta interpretar como CSV-like
    for sep, label in [(",", ","), (";", ";"), ("\t", "tab"), ("|", "|")]:
        if content.count(sep) >= 10:
            try:
                df = pd.read_csv(StringIO(content), sep=sep, on_bad_lines="skip")
                if len(df.columns) >= 2 and len(df) >= 2:
                    return {"kind": "table", "df": df, "text": None,
                            "file_type": f"TXT estruturado (separador '{label}')"}
            except Exception:
                pass

    return {"kind": "text", "df": None, "text": content, "file_type": "TXT"}


# =============================================================================
# Resumos
# =============================================================================

def get_summary(df: pd.DataFrame) -> dict:
    """
    Gera um resumo completo do DataFrame para uso em gráficos, insights e chat.
    Veja CLAUDE.md para a estrutura completa retornada.
    """
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    date_cols = [
        c for c in df.columns
        if pd.api.types.is_datetime64_any_dtype(df[c])
        or "data" in c.lower() or "date" in c.lower() or "dt_" in c.lower()
    ]

    # describe() retorna numpy.float64 — convertemos para float nativo (NaN → None)
    describe = {}
    if numeric_cols:
        desc = df[numeric_cols].describe().round(4)
        describe = {
            col: {stat: (float(val) if pd.notna(val) else None)
                  for stat, val in stats.items()}
            for col, stats in desc.to_dict().items()
        }

    null_counts = df.isnull().sum().to_dict()
    null_counts = {k: int(v) for k, v in null_counts.items() if v > 0}

    groupby_stats = _compute_groupby(df, numeric_cols, date_cols)

    return {
        "kind": "table",
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "column_names": df.columns.tolist(),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "numeric_columns": numeric_cols,
        "date_columns": date_cols,
        "null_counts": null_counts,
        "describe": describe,
        "groupby_stats": groupby_stats,
        "head": df.head(20).fillna("").astype(str).to_dict(orient="records"),
    }


def get_text_summary(text: str, file_type: str) -> dict:
    """
    Resumo para arquivos sem estrutura tabular (PDF/HTML/TXT só com texto).
    Inclui contagens básicas e o conteúdo truncado para análise pela IA.
    """
    text = text or ""
    lines = text.splitlines()
    words = text.split()
    non_empty_lines = [ln for ln in lines if ln.strip()]

    return {
        "kind": "text",
        "file_type": file_type,
        "char_count": len(text),
        "word_count": len(words),
        "line_count": len(non_empty_lines),
        "preview": text[:3000],
        # Truncado para caber no contexto da IA sem estourar tokens
        "full_text": text[:30000],
        "truncated": len(text) > 30000,
    }


def _compute_groupby(df: pd.DataFrame, numeric_cols: list, date_cols: list) -> dict:
    """
    Para cada coluna categórica, calcula a soma das colunas numéricas
    agrupada por valor — top 20 valores. Permite que a IA responda perguntas
    como "qual cliente comprou mais" ou "qual produto tem maior faturamento".
    """
    result = {}
    cat_cols = [
        c for c in df.select_dtypes(include=["object", "category"]).columns
        if c not in date_cols
    ]
    for cat_col in cat_cols[:5]:
        n_unique = df[cat_col].nunique()
        if n_unique < 2 or n_unique > 500:
            continue
        for num_col in numeric_cols[:4]:
            grouped = (
                df.groupby(cat_col, observed=True)[num_col]
                .sum()
                .sort_values(ascending=False)
                .head(20)
            )
            key = f"{cat_col} | {num_col} (soma, top 20)"
            result[key] = {str(k): round(float(v), 4) for k, v in grouped.items()}
    return result
