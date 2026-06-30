"""
ingestion/create_kb.py
One-time run: creates Bedrock Knowledge Base with two data sources
(catalog metadata + unstructured docs) backed by Aurora pgvector.

After running, copy the KB_ID and DS IDs printed at the end into .env

Usage:
    python ingestion/create_kb.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3
import time
import config

bedrock_agent = boto3.client("bedrock-agent", region_name=config.AWS_REGION)

KB_ROLE_ARN = (
    f"arn:aws:iam::{config.AWS_ACCOUNT_ID}:role/BedrockKBRole"
)

SEMANTIC_CHUNK = {
    "chunkingStrategy": "SEMANTIC",
    "semanticChunkingConfiguration": {
        "maxTokens":                     300,
        "bufferSize":                    1,
        "breakpointPercentileThreshold": 95
    }
}


def create_kb() -> str:
    print("Creating Bedrock Knowledge Base...")
    r = bedrock_agent.create_knowledge_base(
        name        = "jay-exer-full-kb",
        description = "Unity Catalog metadata + unstructured S3 docs for jay-exer",
        roleArn     = KB_ROLE_ARN,
        knowledgeBaseConfiguration = {
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn":
                    f"arn:aws:bedrock:{config.AWS_REGION}::foundation-model/{config.BEDROCK_EMBED_MODEL}"
            }
        },
        storageConfiguration = {
            "type": "RDS",
            "rdsConfiguration": {
                "resourceArn":          config.AURORA_CLUSTER_ARN,
                "credentialsSecretArn": config.AURORA_SECRET_ARN,
                "databaseName":         config.AURORA_DB_NAME,
                "tableName":            config.AURORA_TABLE_NAME,
                "fieldMapping": {
                    "primaryKeyField": "id",
                    "vectorField":     "embedding",
                    "textField":       "text",
                    "metadataField":   "metadata"
                }
            }
        }
    )
    kb_id = r["knowledgeBase"]["knowledgeBaseId"]
    print(f"  KB ID: {kb_id}")
    return kb_id


def add_data_source(kb_id: str, name: str, prefix: str) -> str:
    print(f"Adding data source: {name} (s3://{config.S3_BUCKET}/{prefix}/)...")
    r = bedrock_agent.create_data_source(
        knowledgeBaseId = kb_id,
        name            = name,
        dataSourceConfiguration = {
            "type": "S3",
            "s3Configuration": {
                "bucketArn":         f"arn:aws:s3:::{config.S3_BUCKET}",
                "inclusionPrefixes": [f"{prefix}/"]
            }
        },
        vectorIngestionConfiguration = {
            "chunkingConfiguration": SEMANTIC_CHUNK
        }
    )
    ds_id = r["dataSource"]["dataSourceId"]
    print(f"  DS ID: {ds_id}")
    return ds_id


def trigger_ingestion(kb_id: str, ds_id: str, name: str):
    print(f"Triggering ingestion for {name}...")
    bedrock_agent.start_ingestion_job(
        knowledgeBaseId = kb_id,
        dataSourceId    = ds_id
    )
    print(f"  Ingestion started — check AWS console for progress.")


if __name__ == "__main__":
    kb_id         = create_kb()
    ds_catalog_id = add_data_source(kb_id, "catalog-metadata",   "catalog")
    ds_unstruct_id= add_data_source(kb_id, "unstructured-docs",  "unstructured")

    trigger_ingestion(kb_id, ds_catalog_id,  "catalog-metadata")
    trigger_ingestion(kb_id, ds_unstruct_id, "unstructured-docs")

    print("\n── Copy these into your .env ──────────────────────")
    print(f"KB_ID={kb_id}")
    print(f"KB_DS_CATALOG_ID={ds_catalog_id}")
    print(f"KB_DS_UNSTRUCTURED_ID={ds_unstruct_id}")
    print("───────────────────────────────────────────────────")
