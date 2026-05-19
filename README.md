# Análise de Dados com IA

Sistema web que aceita arquivos CSV ou Excel, gera gráficos interativos (histogramas, correlação, tendências temporais) e fornece insights em linguagem natural via OpenAI (GPT-4o mini).

## Estrutura

```
Analise-de-dados-IA/
├── backend/
│   ├── main.py          # FastAPI — rota /upload e /health
│   ├── processor.py     # Leitura e estatísticas com Pandas
│   ├── charts.py        # Geração de gráficos Plotly
│   ├── analyzer.py      # Insights via Claude API
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .env.example
└── README.md
```

## Pré-requisitos

- Python 3.10 ou superior
- pip

## Configuração

### 1. Clonar / entrar no diretório

```bash
cd Analise-de-dados-IA
```

### 2. Configurar variáveis de ambiente

```bash
# Windows (PowerShell)
copy .env.example backend\.env
# Edite backend\.env com sua OPENAI_API_KEY

# Linux/Mac
cp .env.example backend/.env
```

Edite `backend/.env` e substitua `sua_chave_aqui` pela sua chave da API Anthropic.  
Obtenha sua chave em: https://platform.openai.com/api-keys

### 3. Instalar dependências Python

```bash
pip install -r backend/requirements.txt
```

### 4. Iniciar o backend

```bash
uvicorn backend.main:app --reload --port 8000
```

O servidor estará disponível em `http://localhost:8000`.  
Documentação automática da API: `http://localhost:8000/docs`

### 5. Abrir o frontend

Abra o arquivo `frontend/index.html` diretamente no navegador.

Ou sirva com o servidor embutido do Python:

```bash
python -m http.server 3000 --directory frontend
```

Acesse `http://localhost:3000`.

## Uso

1. Na interface web, arraste um arquivo CSV ou Excel (`.xlsx`, `.xls`) para a área indicada, ou clique em **Selecionar arquivo**.
2. Aguarde o processamento (alguns segundos dependendo do tamanho do arquivo).
3. Visualize os gráficos interativos e leia os insights gerados pela IA na seção **Insights da IA**.
4. Clique em **Resumo Estatístico** para ver estatísticas descritivas detalhadas.
5. Clique em **Nova análise** para carregar outro arquivo.

## Gráficos gerados

| Gráfico | Condição |
|---|---|
| Histograma de distribuição | Uma por coluna numérica (máx. 3) |
| Mapa de correlação (heatmap) | Quando há 2 ou mais colunas numéricas |
| Gráfico de tendência temporal | Quando uma coluna de data é detectada |

## Formatos suportados

- `.csv` (UTF-8)
- `.xlsx` (Excel 2007+)
- `.xls` (Excel legado)

## Sem chave de API

O sistema funciona sem a chave da OpenAI — gráficos e estatísticas são gerados normalmente. Apenas os insights de texto da IA ficam desabilitados.
