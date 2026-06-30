"""
agent/tools.py
All ReActAgent tool functions:
  - catalog_search       → hybrid search over Unity Catalog metadata
  - unstructured_search  → hybrid search over S3 PDFs/docs
  - run_sql              → execute SELECT against jay-exer Databricks
  - get_column_samples   → distinct values for WHERE filter accuracy
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import boto3
from databricks import sql as dbsql
import config

bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=config.AWS_REGION)

_conn = None

def _get_conn():
    global _conn
    if _conn is None:
        _conn = dbsql.connect(
            server_hostname = config.DATABRICKS_HOST.replace("https://", ""),
            http_path       = config.DATABRICKS_HTTP_PATH,
            access_token    = config.DATABRICKS_TOKEN
        )
    return _conn


def _kb_search(question: str, source_prefix: str, top_k: int = 5) -> list[dict]:
    """Internal helper — hybrid search against Bedrock KB with prefix filter."""
    response = bedrock_runtime.retrieve(
        knowledgeBaseId = config.KB_ID,
        retrievalQuery  = {"text": question},
        retrievalConfiguration = {
            "vectorSearchConfiguration": {
                "numberOfResults":    top_k,
                "overrideSearchType": "HYBRID",
            }
        }
    )
    results = []
    for r in response["retrievalResults"]:
        meta = r.get("metadata", {})
        # Filter by source prefix in metadata (catalog vs unstructured)
        uri = r.get("location", {}).get("s3Location", {}).get("uri", "")

        if source_prefix == "catalog" and "/catalog/" not in uri:
            continue
        if source_prefix == "unstructured" and "/unstructured/" not in uri:
            continue
        results.append({
            "score":   round(r["score"], 3),
            "content": r["content"]["text"],
            "source":  uri,
            "table":   meta.get("full_path", ""),
            "layer":   meta.get("layer", "")
        })
    return results


def catalog_search(question: str) -> str:
    """
    Semantic + keyword hybrid search over jay-exer Unity Catalog metadata
    (table names, column names, business descriptions, sample values).
    Always call this before writing any SQL — never guess table or column names.
    Returns relevant table schemas as JSON.
    """
    results = _kb_search(question, source_prefix="catalog", top_k=5)
    if not results:
        return json.dumps({"message": "No relevant catalog entries found. Try rephrasing."})
    return json.dumps(results, indent=2)


def unstructured_search(question: str) -> str:
    """
    Semantic + keyword hybrid search over unstructured S3 documents
    (PDFs, reports, JSON files, text files).
    Use for factual questions that don't need SQL — e.g. policy docs, reports, summaries.
    Returns relevant document excerpts as JSON.
    """
    results = _kb_search(question, source_prefix="unstructured", top_k=5)
    if not results:
        return json.dumps({"message": "No relevant documents found. Try rephrasing."})
    return json.dumps(results, indent=2)


def run_sql(sql: str) -> str:
    """
    Execute a read-only SQL SELECT query against the jay-exer Databricks catalog.
    Always use full table path: jay-exer.schema.table_name
    Returns rows as JSON with columns list — the UI will auto-chart results.
    Only SELECT statements are permitted — never INSERT, UPDATE, DELETE, DROP.
    """
    sql_clean = sql.strip()
    if not sql_clean.upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are permitted."})
    try:
        conn   = _get_conn()
        cursor = conn.cursor()
        cursor.execute(sql_clean)
        rows    = cursor.fetchmany(500)
        columns = [d[0] for d in cursor.description]
        data    = [dict(zip(columns, r)) for r in rows]
        return json.dumps({
            "columns":    columns,
            "rows":       data,
            "row_count":  len(data)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_column_samples(full_table_path: str, column_name: str) -> str:
    """
    Get distinct sample values for a specific column in a Databricks table.
    Use this before building WHERE clause filters to ensure accurate values.
    full_table_path format: jay-exer.schema_name.table_name
    """
    try:
        conn   = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT {column_name} FROM {full_table_path} LIMIT 10"
        )
        values = [str(r[0]) for r in cursor.fetchall()]
        return json.dumps({"column": column_name, "sample_values": values})
    except Exception as e:
        return json.dumps({"error": str(e)})
