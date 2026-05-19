# DataInsight AI — Contexto do Projeto

Sistema web de análise de dados com IA: o usuário faz upload de um arquivo (CSV, Excel, PDF, HTML ou TXT), recebe gráficos interativos, estatísticas descritivas, insights automáticos via OpenAI e pode conversar com um assistente sobre o conteúdo.

O sistema funciona em **dois modos**:
- **Modo tabela** (CSV/Excel ou PDF/HTML/TXT com estrutura tabular detectada) → pipeline completo com gráficos, stats e groupby.
- **Modo texto** (PDF/HTML/TXT sem tabelas) → análise do conteúdo via IA, sem gráficos.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI (Python 3.13) |
| Processamento tabular | Pandas + openpyxl + xlrd |
| Extração de texto | pdfplumber (PDF) + BeautifulSoup + lxml (HTML) |
| Gráficos | Plotly (JSON → renderizado pelo Plotly.js no browser) |
| IA | OpenAI SDK v2 (`openai==2.37.0`), modelo `gpt-4o-mini` |
| Frontend | HTML + CSS + Vanilla JS (Inter font via Google Fonts) |
| Servidor de arquivos estáticos | Próprio FastAPI via `StaticFiles` |

---

## Estrutura de arquivos

```
Analise-de-dados-IA/
├── backend/
│   ├── __init__.py       # Necessário para importar como pacote (from backend.x import ...)
│   ├── main.py           # FastAPI: rotas /health, /upload, /chat + serve o frontend
│   ├── processor.py      # Leitura multi-formato + get_summary() + get_text_summary()
│   ├── charts.py         # Plotly: histogramas, heatmap de correlação, linha temporal
│   ├── analyzer.py       # OpenAI: insights e chat, com dispatch por tipo (table/text)
│   ├── requirements.txt
│   └── .env              # OPENAI_API_KEY=sk-... (não commitado)
├── frontend/
│   ├── index.html        # UI completa: topbar, upload, loading, error, results, chat, footer
│   ├── style.css         # Design profissional (Inter, KPI cards, sombras, SVG icons)
│   └── app.js            # Fetch API, Plotly.newPlot(), KPIs adaptáveis, chat com histórico
├── .env.example          # Template: OPENAI_API_KEY=sua_chave_aqui
├── CLAUDE.md             # Este arquivo
└── README.md             # Instruções de instalação e uso
```

---

## Como rodar

```powershell
# 1. Instalar dependências (apenas na primeira vez)
pip install -r backend\requirements.txt

# 2. Configurar chave da API (apenas na primeira vez)
copy .env.example backend\.env
# editar backend\.env e colocar a chave real da OpenAI

# 3. Subir o servidor (a partir da raiz do projeto)
uvicorn backend.main:app --reload --port 8000

# 4. Abrir no browser
# http://localhost:8000
```

> **Importante:** o frontend é servido pelo próprio FastAPI via `StaticFiles`. Não abra o `index.html` diretamente pelo sistema de arquivos (`file://`) — isso causa erro de CORS com origem `null`.
>
> Quando você instalar novos pacotes, **reinicie o uvicorn** — o `--reload` só detecta mudanças em arquivos `.py`, não novos pacotes.

---

## Formatos de arquivo suportados

| Extensão | Tabela detectada? | Comportamento |
|---|---|---|
| `.csv` | Sempre | Modo tabela |
| `.xlsx` / `.xls` | Sempre | Modo tabela |
| `.pdf` | Sim (via `pdfplumber`) | Modo tabela — usa a maior tabela encontrada, tenta converter colunas com vírgula decimal |
| `.pdf` | Não | Modo texto — extrai todo o texto das páginas |
| `.html` / `.htm` | Tem `<table>` | Modo tabela — usa a maior tabela via `pd.read_html()` |
| `.html` / `.htm` | Sem `<table>` | Modo texto — extrai texto limpo via BeautifulSoup (remove `<script>`, `<style>`, `<noscript>`) |
| `.txt` | Tem separador (`,` `;` `\t` `\|` com 10+ ocorrências e ≥ 2 colunas detectadas) | Modo tabela — parsing com o separador detectado |
| `.txt` | Sem estrutura | Modo texto |

`read_file(path)` retorna sempre um dict: `{kind, df, text, file_type}`. O `kind` é `"table"` ou `"text"` e direciona todo o resto do pipeline.

---

## Decisões arquiteturais importantes

### Por que `from backend.x import` em vez de `from x import`?
O uvicorn é iniciado da **raiz do projeto** com `uvicorn backend.main:app`. Nesse contexto, `backend` é o pacote e os módulos precisam ser importados com o prefixo `backend.`. Se rodar de dentro da pasta `backend/` com `uvicorn main:app`, as importações simples funcionariam — mas o padrão adotado é rodar da raiz.

### Por que o `StaticFiles` fica no final do `main.py`?
O mount `app.mount("/", StaticFiles(...))` captura **todas** as rotas não definidas. Se ficar antes das rotas da API, interceptaria `/upload` e `/chat`. Por isso deve sempre ser a última linha de configuração do app.

### Por que os valores do `describe()` são convertidos para `float`?
`pandas.DataFrame.describe().to_dict()` retorna `numpy.float64`, que **não é serializável em JSON** pelo FastAPI. Todos os valores são convertidos para `float` Python nativo, e `NaN` é convertido para `None`.

### Por que o `groupby_stats` existe no summary?
O chat inicialmente não conseguia responder "qual cliente comprou mais" porque só tinha acesso às estatísticas descritivas globais (média, max, etc.). O `groupby_stats` pré-computa a soma de colunas numéricas agrupada por cada coluna categórica (top 20), permitindo respostas precisas sobre rankings e totais por categoria.

### Por que o backend é stateless no chat?
O frontend envia o `summary` completo + histórico de mensagens a cada requisição do chat. Isso simplifica o backend (sem sessão/estado) e permite que o servidor seja reiniciado sem perder contexto do usuário.

### Por que o `load_dotenv` recebe o caminho explícito?
```python
load_dotenv(Path(__file__).parent / ".env")
```
Sem o caminho explícito, `load_dotenv()` procura o `.env` no diretório de trabalho atual (raiz do projeto). O arquivo `.env` fica em `backend/.env`, então o caminho precisa ser resolvido em relação ao `main.py`.

### Por que o summary tem o campo `kind`?
Para que `get_insights()` e `chat_with_data()` possam fazer **dispatch** entre o pipeline tabular (estatísticas + groupby) e o pipeline textual (conteúdo bruto). O frontend também usa `kind` para esconder os gráficos e a tabela de stats quando o arquivo é só texto.

### Por que o texto é truncado em 30.000 caracteres?
Para não estourar o context window do `gpt-4o-mini`. Quando o conteúdo extraído ultrapassa esse limite, o flag `truncated: true` é incluído no summary e a IA é avisada via prompt.

### Por que tentamos converter colunas de PDF para numérico?
Tabelas extraídas de PDFs vêm como strings, inclusive valores monetários no formato brasileiro (`1.234,56`). Quando mais de 70% das células de uma coluna são convertíveis após substituir `,` por `.`, a coluna inteira vira numérica — habilitando gráficos e estatísticas.

---

## Rotas da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check — retorna `{"status": "ok"}` |
| `POST` | `/upload` | Recebe arquivo multipart, retorna `{filename, summary, charts, insights}` |
| `POST` | `/chat` | Recebe `{question, summary, history}`, retorna `{answer}` |
| `GET` | `/*` | Serve os arquivos estáticos do frontend |

---

## Estrutura do objeto `summary`

### Modo tabela (`kind: "table"`)
```json
{
  "kind": "table",
  "file_type": "Excel" | "CSV" | "PDF (3 tabela(s) detectada(s))" | ...,
  "rows": 1500,
  "columns": 8,
  "column_names": ["Razão Social", "Valor total do pedido", ...],
  "dtypes": {"Razão Social": "object", "Valor total do pedido": "float64"},
  "numeric_columns": ["Valor total do pedido", ...],
  "date_columns": ["Data do pedido"],
  "null_counts": {"Observação": 120},
  "describe": {
    "Valor total do pedido": {"count": 1500.0, "mean": 4200.5, "std": 890.2, ...}
  },
  "groupby_stats": {
    "Razão Social | Valor total do pedido (soma, top 20)": {
      "Cliente X": 2732902.75,
      "Cliente Y": 1850000.00
    }
  },
  "head": [{"Razão Social": "Cliente X", "Valor total do pedido": "1200.00", ...}]
}
```

### Modo texto (`kind: "text"`)
```json
{
  "kind": "text",
  "file_type": "PDF" | "HTML" | "TXT",
  "char_count": 12345,
  "word_count": 2300,
  "line_count": 150,
  "preview": "primeiros 3.000 chars...",
  "full_text": "primeiros 30.000 chars (enviado à IA)",
  "truncated": false
}
```

---

## Limites e comportamento do `groupby_stats`

- Processa até **5 colunas categóricas** (tipo `object` ou `category`)
- Processa até **4 colunas numéricas** por coluna categórica
- Retorna **top 20** valores por combinação, ordenados por soma decrescente
- Ignora colunas com menos de 2 ou mais de 500 valores únicos (evita IDs únicos e constantes)
- Exclui colunas detectadas como datas

---

## Formato de gráficos retornados pelo `/upload` (apenas modo tabela)

Cada item da lista `charts` tem:
```json
{
  "title": "Distribuição: Valor total do pedido",
  "data": { ...plotly_figure_json... }
}
```
O frontend usa `Plotly.newPlot(div, chart.data.data, { ...chart.data.layout, height: 320 })`.

No modo texto, `charts` é sempre `[]` e o frontend esconde a seção de gráficos via `.hidden`.

---

## Histórico do chat

- O frontend mantém `chatHistory` em memória (array de `{role, content}`)
- Limitado a **20 mensagens** (10 trocas) para controlar custo de tokens
- O histórico é **zerado** ao fazer um novo upload
- O backend não armazena estado — recebe o histórico completo a cada requisição

---

## Frontend — comportamento dos KPIs

Os 4 KPI cards no topo da seção de resultados se adaptam ao tipo do arquivo:

| Modo | KPI 1 | KPI 2 | KPI 3 | KPI 4 |
|---|---|---|---|---|
| Tabela | Linhas | Colunas | Numéricas | Com nulos |
| Texto | Palavras | Linhas | Caracteres | Tipo (PDF/HTML/TXT) |

A função `setKPI(id, value, label)` em `app.js` atualiza tanto o valor quanto o rótulo dinamicamente.

---

## Frontend — Resumo Estatístico em PT-BR

A tabela de estatísticas usa um mapa de tradução `STAT_LABELS` em `app.js`:

| Pandas | Exibido |
|---|---|
| count | Contagem |
| mean | Média |
| std | Desvio padrão |
| min | Mínimo |
| 25% | 1º quartil (25%) |
| 50% | Mediana (50%) |
| 75% | 3º quartil (75%) |
| max | Máximo |

A linha "Contagem" é formatada como inteiro; as demais com até 4 casas decimais usando `toLocaleString("pt-BR")`.

---

## Problemas conhecidos e resolvidos

| Problema | Causa | Solução |
|---|---|---|
| `ModuleNotFoundError: No module named 'processor'` | Importações relativas sem prefixo de pacote | Usar `from backend.x import` + criar `__init__.py` |
| `500` com "Internal Server Error" no upload | `numpy.float64` não serializável em JSON | Converter todos os valores do `describe` para `float` Python |
| CORS com `file://` | Browser trata `file://` como origem `null` | Servir o frontend pelo próprio FastAPI via `StaticFiles` |
| `openai==1.59.0` não encontrada | Versão inexistente no PyPI | Usar `openai==2.37.0` |
| `xlrd` ausente | Pacote opcional não instalado | Adicionar `xlrd==2.0.1` ao `requirements.txt` |
| Chat não sabia "qual cliente comprou mais" | Só tinha estatísticas globais, sem dados agrupados | Adicionar `groupby_stats` ao summary |
| `No module named 'pdfplumber'` ao subir PDF | Dependência não instalada após edição do requirements | Reinstalar com `pip install -r backend/requirements.txt` e reiniciar uvicorn |

---

## Dependências (`backend/requirements.txt`)

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
pandas==2.2.3
openpyxl==3.1.5
xlrd==2.0.1
plotly==5.24.1
openai==2.37.0
python-multipart==0.0.17
python-dotenv==1.0.1
pdfplumber==0.11.4
beautifulsoup4==4.12.3
lxml==5.3.0
```

---

## Histórico evolutivo do projeto

1. **MVP inicial**: upload de CSV/Excel → estatísticas + gráficos + insights da IA
2. **Trocou Anthropic por OpenAI**: usuário já tinha conta no OpenAI
3. **Correção de bugs**: numpy serialization, imports relativos, CORS, xlrd
4. **Chat adicionado**: histórico mantido no frontend, backend stateless
5. **Groupby stats**: para que o chat respondesse perguntas como "qual cliente comprou mais"
6. **Comentários completos**: docstrings em todos os arquivos Python e JS
7. **Redesign profissional**: Inter font, topbar, KPI cards, sombras, SVG icons
8. **Resumo estatístico em PT-BR**: tradução dos rótulos do `describe()`
9. **Suporte a PDF/HTML/TXT**: extração de tabelas quando possível, fallback para análise de texto
