"""
agent/react_agent.py
ReActAgent using LlamaIndex + Claude Sonnet via AWS Bedrock.
Orchestrates: catalog_search → run_sql → unstructured_search → answer
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import re
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.bedrock import Bedrock
import config
from agent.tools import (
    catalog_search,
    unstructured_search,
    run_sql,
    get_column_samples
)

SYSTEM_PROMPT = """
You are a senior data analyst with access to two data sources:

1. jay-exer Databricks Unity Catalog (bronze / silver / gold medallion layers)
   - bronze = raw ingested data
   - silver = cleansed and conformed
   - gold   = aggregated business metrics — prefer for KPIs and reporting

2. Unstructured S3 documents (PDFs, reports, JSON files, text)

Decision rules — follow in order:
- Is this a metrics / aggregation / trend question?
  → Step 1: catalog_search to find the right table and columns
  → Step 2: get_column_samples if you need to check filter values
  → Step 3: run_sql with the full path jay-exer.schema.table
- Is this a document / policy / report question?
  → unstructured_search
- Is this mixed (e.g. "compare report finding to actual data")?
  → Do both, synthesize the answer

Strict rules:
- NEVER guess table or column names — always call catalog_search first
- NEVER run INSERT, UPDATE, DELETE, DROP — SELECT only
- Always use full path in SQL: jay-exer.schema_name.table_name
- If SQL returns an error, read it and self-correct — retry with fixed SQL
- Keep answers concise and data-grounded
"""


def build_agent() -> ReActAgent:
    llm = Bedrock(
        model      = config.BEDROCK_LLM_MODEL,
        region     = config.AWS_REGION,
        max_tokens = 2048 ,
        temperature = 0.0,
        context_size = 200000
    )

    tools = [
        FunctionTool.from_defaults(fn=catalog_search),
        FunctionTool.from_defaults(fn=unstructured_search),
        FunctionTool.from_defaults(fn=run_sql),
        FunctionTool.from_defaults(fn=get_column_samples),
    ]

    return ReActAgent.from_tools(
        tools          = tools,
        llm            = llm,
        verbose        = True,
        max_iterations = 12,
        system_prompt  = SYSTEM_PROMPT
    )


# Singleton agent — one instance per process
_agent = None

def get_agent() -> ReActAgent:
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def query(question: str) -> dict:
    """
    Run the agent and return a structured dict for the Streamlit UI.
    Returns:
        {
          "answer":   str,           # natural language answer
          "sql_data": dict | None,   # {"columns": [...], "rows": [...]} if SQL was run
          "sources":  list[str]      # S3 URIs of retrieved documents
        }
    """
    agent    = get_agent()
    response = agent.chat(question)
    text     = str(response)

    # Extract SQL result JSON if present in the agent trace
    sql_data = None
    match = re.search(r'\{"columns":\s*\[.*?"rows":\s*\[.*?\]\}', text, re.DOTALL)
    if match:
        try:
            sql_data = json.loads(match.group())
        except Exception:
            pass

    return {
        "answer":   text,
        "sql_data": sql_data,
        "sources":  []
    }
