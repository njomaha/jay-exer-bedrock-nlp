"""
ingestion/extract_catalog.py
Extracts Unity Catalog metadata from jay-exer Databricks workspace
and uploads rich text descriptions to S3 under catalog/ prefix.

Usage:
    python ingestion/extract_catalog.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import boto3
from databricks import sql as dbsql
import config

s3 = boto3.client("s3", region_name=config.AWS_REGION)


def get_connection():
    return dbsql.connect(
        server_hostname = config.DATABRICKS_HOST.replace("https://", ""),
        http_path       = config.DATABRICKS_HTTP_PATH,
        access_token    = config.DATABRICKS_TOKEN
    )


def extract_unity_catalog(catalog: str = "jay-exer") -> list[dict]:
    conn   = get_connection()
    cursor = conn.cursor()
    entries = []

    cursor.execute(f"SHOW SCHEMAS IN `{catalog}`")
    schemas = [r[0] for r in cursor.fetchall()]

    for schema in schemas:
        cursor.execute(f"SHOW TABLES IN `{catalog}`.`{schema}`")
        tables = [r[1] for r in cursor.fetchall()]

        for table in tables:
            full_path = f"`{catalog}`.`{schema}`.`{table}`"

            # Column metadata
            cursor.execute(f"DESCRIBE TABLE EXTENDED {full_path}")
            rows = cursor.fetchall()
            columns = [
                {"name": r[0], "type": r[1], "comment": r[2] or ""}
                for r in rows
                if r[0] and not r[0].startswith("#")
            ]

            # Sample values (top 5 columns only to avoid rate limits)
            sample_data = {}
            for col in columns[:5]:
                try:
                    cursor.execute(
                        f"SELECT DISTINCT {col['name']} "
                        f"FROM {full_path} LIMIT 5"
                    )
                    sample_data[col["name"]] = [str(r[0]) for r in cursor.fetchall()]
                except Exception:
                    pass

            layer_desc = {
                "bronze": "raw ingestion — unprocessed source data",
                "silver": "cleansed and conformed data",
                "gold":   "aggregated business metrics — use for KPIs and reporting"
            }.get(schema, schema)

            text = f"""Catalog: {catalog}
Schema: {schema}
Table: {table}
Full Path: {catalog}.{schema}.{table}
Layer: {schema} ({layer_desc})
Business terms: {table.replace("_", " ")}

Columns:
{json.dumps(columns, indent=2)}

Sample values:
{json.dumps(sample_data, indent=2)}
"""
            entries.append({
                "id":       f"{catalog}.{schema}.{table}",
                "text":     text.strip(),
                "metadata": {
                    "full_path":   f"{catalog}.{schema}.{table}",
                    "catalog":     catalog,
                    "schema":      schema,
                    "table":       table,
                    "layer":       schema,
                    "source_prefix": "catalog"
                }
            })

    conn.close()
    return entries


def upload_to_s3(entries: list[dict]):
    for entry in entries:
        key = "catalog/{}.txt".format(entry["id"].replace(".", "/"))
        body = entry["text"] + "\n\n---METADATA---\n" + json.dumps(entry["metadata"])
        s3.put_object(
            Bucket      = config.S3_BUCKET,
            Key         = key,
            Body        = body.encode("utf-8"),
            ContentType = "text/plain"
        )
    print(f"Uploaded {len(entries)} catalog entries → s3://{config.S3_BUCKET}/catalog/")


if __name__ == "__main__":
    print("Extracting Unity Catalog metadata from jay-exer...")
    entries = extract_unity_catalog(config.DATABRICKS_CATALOG)
    print(f"Extracted {len(entries)} tables")
    upload_to_s3(entries)
