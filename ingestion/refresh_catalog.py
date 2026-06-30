"""
ingestion/refresh_catalog.py
Re-extracts Unity Catalog metadata and re-triggers KB ingestion.
Schedule this as a Windows Task Scheduler job or Databricks Workflow (daily).

Usage:
    python ingestion/refresh_catalog.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3
import config
from ingestion.extract_catalog import extract_unity_catalog, upload_to_s3

bedrock_agent = boto3.client("bedrock-agent", region_name=config.AWS_REGION)


def refresh():
    print("Step 1 — Re-extracting Unity Catalog metadata...")
    entries = extract_unity_catalog(config.DATABRICKS_CATALOG)
    upload_to_s3(entries)

    print("Step 2 — Re-triggering Bedrock KB ingestion...")
    bedrock_agent.start_ingestion_job(
        knowledgeBaseId = config.KB_ID,
        dataSourceId    = config.KB_DS_CATALOG_ID
    )
    print("  Catalog ingestion triggered.")
    print("Done — index will be updated within a few minutes.")


if __name__ == "__main__":
    refresh()
