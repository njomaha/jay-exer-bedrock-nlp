import os
from dotenv import load_dotenv

load_dotenv()

# AWS
AWS_REGION     = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID", "640470426630")

# Bedrock
BEDROCK_EMBED_MODEL = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
BEDROCK_LLM_MODEL   = os.getenv("BEDROCK_LLM_MODEL",   "us.anthropic.claude-sonnet-4-20250514-v1:0")

# Knowledge Base
KB_ID               = os.getenv("KB_ID", "")
KB_DS_CATALOG_ID    = os.getenv("KB_DS_CATALOG_ID", "")
KB_DS_UNSTRUCTURED_ID = os.getenv("KB_DS_UNSTRUCTURED_ID", "")

# S3
S3_BUCKET = os.getenv("S3_BUCKET", "jay-exer-catalog-rag")

# Aurora pgvector
AURORA_CLUSTER_ARN = os.getenv("AURORA_CLUSTER_ARN", "")
AURORA_SECRET_ARN  = os.getenv("AURORA_SECRET_ARN", "")
AURORA_DB_NAME     = os.getenv("AURORA_DB_NAME", "catalog_rag")
AURORA_TABLE_NAME  = os.getenv("AURORA_TABLE_NAME", "bedrock_kb")

# Databricks
DATABRICKS_HOST      = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH", "")
DATABRICKS_TOKEN     = os.getenv("DATABRICKS_TOKEN", "")
DATABRICKS_CATALOG   = os.getenv("DATABRICKS_CATALOG", "jay-exer")
