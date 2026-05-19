"""
main.py — Ponto de entrada da API FastAPI.

Rotas disponíveis:
  GET  /health  → verifica se o servidor está no ar
  POST /upload  → recebe um arquivo CSV/Excel, processa e retorna gráficos + insights
  POST /chat    → responde perguntas sobre o arquivo já carregado
  GET  /        → serve o frontend estático (index.html)
"""

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Carrega as variáveis de ambiente do arquivo .env localizado na pasta backend/
load_dotenv(Path(__file__).parent / ".env")

from backend.processor import get_summary, get_text_summary, read_file
from backend.charts import generate_charts
from backend.analyzer import get_insights, chat_with_data

app = FastAPI(title="Análise de Dados com IA")

# Extensões de arquivo aceitas no upload
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf", ".html", ".htm", ".txt"}


@app.get("/health")
def health():
    """Verifica se a API está respondendo."""
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Recebe um arquivo CSV ou Excel, processa os dados e retorna:
    - summary: estatísticas descritivas e dados agrupados por categoria
    - charts:  lista de gráficos Plotly em formato JSON
    - insights: análise em linguagem natural gerada pela IA
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {ext}. Use CSV, Excel, PDF, HTML ou TXT."
        )

    tmp_path = None
    try:
        # Salva o arquivo em disco temporariamente para o leitor poder acessar
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        try:
            result = read_file(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Erro ao ler o arquivo: {e}")

        # Dois caminhos de processamento: tabela (DataFrame) ou texto puro
        try:
            if result["kind"] == "table":
                df = result["df"]
                if df is None or df.empty:
                    raise HTTPException(status_code=422, detail="O arquivo está vazio ou não possui dados válidos.")
                summary = get_summary(df)
                summary["file_type"] = result["file_type"]
                charts = generate_charts(df)
            else:
                text = result["text"] or ""
                if not text.strip():
                    raise HTTPException(status_code=422, detail="Não foi possível extrair conteúdo do arquivo.")
                summary = get_text_summary(text, result["file_type"])
                charts = []  # arquivos de texto não geram gráficos
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao processar os dados: {e}")

        # A geração de insights é opcional: se a chave não estiver configurada,
        # retorna uma mensagem orientando o usuário em vez de lançar erro.
        api_key = os.environ.get("OPENAI_API_KEY", "")
        insights = ""
        if api_key:
            try:
                insights = get_insights(summary)
            except Exception as e:
                insights = f"(Não foi possível gerar insights via IA: {e})"
        else:
            insights = "Configure OPENAI_API_KEY no arquivo .env para obter insights de IA."

        return {
            "filename": file.filename,
            "summary": summary,
            "charts": charts,
            "insights": insights,
        }

    finally:
        # Garante que o arquivo temporário seja removido mesmo em caso de erro
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


# --- Modelos de dados para o endpoint de chat ---

class ChatMessage(BaseModel):
    """Uma mensagem do histórico da conversa (role: 'user' ou 'assistant')."""
    role: str
    content: str

class ChatRequest(BaseModel):
    """Corpo da requisição POST /chat."""
    question: str                    # Pergunta feita pelo usuário
    summary: dict                    # Resumo do arquivo, enviado pelo frontend a cada mensagem
    history: list[ChatMessage] = []  # Histórico das mensagens anteriores para manter contexto


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Recebe uma pergunta sobre os dados do arquivo carregado e retorna
    a resposta gerada pela IA com base no summary e no histórico da conversa.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY não configurada.")
    try:
        # Converte os objetos Pydantic para dicts simples esperados pela OpenAI
        history = [{"role": m.role, "content": m.content} for m in req.history]
        answer = chat_with_data(req.question, req.summary, history)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar resposta: {e}")


# Monta o frontend como arquivos estáticos.
# Deve ficar APÓS todas as rotas da API para não interceptar /upload e /chat.
_frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
