"""
analyzer.py — Integração com a OpenAI para insights e chat.

Funções públicas:
  get_insights(summary)                       → análise inicial do arquivo
  chat_with_data(question, summary, history)  → responde perguntas em conversa

Ambas as funções aceitam dois tipos de summary, identificados por summary["kind"]:
  - "table" → DataFrame com estatísticas, dados agrupados, etc.
  - "text"  → texto puro extraído de PDF/HTML/TXT
"""

import os
import json
from openai import OpenAI

MODEL = "gpt-4o-mini"


def get_insights(summary: dict) -> str:
    """
    Gera uma análise automática do arquivo logo após o upload.
    Despacha entre análise tabular ou textual conforme o tipo do summary.
    """
    if summary.get("kind") == "text":
        return _insights_for_text(summary)
    return _insights_for_table(summary)


def chat_with_data(question: str, summary: dict, history: list[dict]) -> str:
    """
    Responde perguntas do usuário sobre o arquivo carregado.
    Despacha entre chat tabular ou textual conforme o tipo do summary.
    """
    if summary.get("kind") == "text":
        return _chat_for_text(question, summary, history)
    return _chat_for_table(question, summary, history)


# =============================================================================
# Modo tabela (CSV/Excel/PDF com tabela/HTML com tabela)
# =============================================================================

def _insights_for_table(summary: dict) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    head_str     = json.dumps(summary.get("head", []),     ensure_ascii=False, indent=2)
    describe_str = json.dumps(summary.get("describe", {}), ensure_ascii=False, indent=2)
    nulls_str    = json.dumps(summary.get("null_counts", {}), ensure_ascii=False)

    prompt = f"""Você é um analista de dados especialista. Analise o conjunto de dados abaixo e forneça insights em português brasileiro.

## Metadados
- Tipo: {summary.get('file_type', 'tabela')}
- Linhas: {summary['rows']}
- Colunas: {summary['columns']}
- Nomes das colunas: {', '.join(summary['column_names'])}
- Colunas numéricas: {', '.join(summary['numeric_columns']) or 'nenhuma'}
- Colunas de data detectadas: {', '.join(summary['date_columns']) or 'nenhuma'}
- Valores nulos por coluna: {nulls_str or 'nenhum'}

## Estatísticas Descritivas
{describe_str}

## Amostra dos Dados
{head_str}

## Tarefa
Forneça:
1. **Visão geral**: O que este dataset parece representar?
2. **Padrões identificados**: Tendências, concentrações ou comportamentos notáveis.
3. **Anomalias ou alertas**: Valores suspeitos, distribuições atípicas, problemas de qualidade.
4. **Recomendações**: 2-3 análises sugeridas para aprofundar o entendimento.

Seja direto e objetivo. Máximo de 300 palavras."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
    )
    return response.choices[0].message.content


def _chat_for_table(question: str, summary: dict, history: list[dict]) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    describe_str = json.dumps(summary.get("describe", {}),     ensure_ascii=False)
    groupby_str  = json.dumps(summary.get("groupby_stats", {}), ensure_ascii=False, indent=2)

    system_prompt = f"""Você é um assistente especialista em análise de dados. O usuário fez upload de um arquivo e você tem acesso ao resumo completo, incluindo dados agrupados por categoria.

## Metadados
- Tipo: {summary.get('file_type', 'tabela')}
- Linhas: {summary['rows']} | Colunas: {summary['columns']}
- Nomes das colunas: {', '.join(summary['column_names'])}
- Colunas numéricas: {', '.join(summary['numeric_columns']) or 'nenhuma'}
- Colunas de data: {', '.join(summary['date_columns']) or 'nenhuma'}
- Valores nulos: {json.dumps(summary.get('null_counts', {}), ensure_ascii=False)}

## Estatísticas descritivas
{describe_str}

## Dados agrupados por categoria (top 20 por soma — use para rankings, totais e comparações)
{groupby_str}

Responda em português brasileiro de forma clara e objetiva. Se a pergunta não puder ser respondida com os dados disponíveis, diga isso claramente."""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=600,
    )
    return response.choices[0].message.content


# =============================================================================
# Modo texto (PDF/HTML/TXT sem estrutura tabular)
# =============================================================================

def _insights_for_text(summary: dict) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    truncated_note = "\n\n[Conteúdo truncado em 30.000 caracteres]" if summary.get("truncated") else ""

    prompt = f"""Você é um analista de documentos. Analise o conteúdo abaixo e forneça insights em português brasileiro.

## Metadados
- Tipo: {summary['file_type']}
- Caracteres: {summary['char_count']:,}
- Palavras: {summary['word_count']:,}
- Linhas não vazias: {summary['line_count']:,}

## Conteúdo
{summary['full_text']}{truncated_note}

## Tarefa
Forneça:
1. **Resumo**: Do que trata este documento?
2. **Pontos principais**: Temas, dados ou informações mais relevantes.
3. **Observações**: Padrões, inconsistências ou pontos que mereçam atenção.
4. **Recomendações**: 2-3 perguntas que valeria a pena investigar.

Seja direto e objetivo. Máximo de 350 palavras."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
    )
    return response.choices[0].message.content


def _chat_for_text(question: str, summary: dict, history: list[dict]) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    truncated_note = "\n\n[Conteúdo truncado em 30.000 caracteres]" if summary.get("truncated") else ""

    system_prompt = f"""Você é um assistente especialista em análise de documentos. O usuário fez upload de um arquivo de texto e você tem acesso ao conteúdo completo abaixo.

## Metadados do documento
- Tipo: {summary['file_type']}
- Caracteres: {summary['char_count']:,}
- Palavras: {summary['word_count']:,}
- Linhas: {summary['line_count']:,}

## Conteúdo do documento
{summary['full_text']}{truncated_note}

Responda perguntas sobre este documento em português brasileiro, de forma clara e objetiva. Use citações do texto quando relevante. Se a pergunta não puder ser respondida com base no conteúdo, diga isso claramente."""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=700,
    )
    return response.choices[0].message.content
