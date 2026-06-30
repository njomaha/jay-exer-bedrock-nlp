"""
ingestion/upload_unstructured.py
Uploads local unstructured docs (PDFs, JSON, txt, md, csv)
from the docs/ folder to S3 under unstructured/ prefix.
Bedrock KB will chunk + embed them automatically.

Usage:
    python ingestion/upload_unstructured.py
    python ingestion/upload_unstructured.py --folder C:\\path\\to\\docs
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
import boto3
from pathlib import Path
import config

s3 = boto3.client("s3", region_name=config.AWS_REGION)

SUPPORTED = {".pdf", ".txt", ".json", ".html", ".md", ".docx", ".csv"}


def upload_docs(folder: str = "docs"):
    docs_path = Path(folder)
    if not docs_path.exists():
        print(f"Folder {folder} not found — creating empty docs/ placeholder.")
        docs_path.mkdir(parents=True, exist_ok=True)
        (docs_path / "README.txt").write_text(
            "Drop your PDFs, JSON, txt, md, csv files here then re-run upload_unstructured.py"
        )

    uploaded = 0
    skipped  = 0
    for f in docs_path.rglob("*"):
        if f.is_file() and f.suffix.lower() in SUPPORTED:
            key = f"unstructured/{f.name}"
            s3.upload_file(
                Filename  = str(f),
                Bucket    = config.S3_BUCKET,
                Key       = key,
                ExtraArgs = {"Metadata": {"source": f.name, "source_prefix": "unstructured"}}
            )
            print(f"  Uploaded: {f.name}")
            uploaded += 1
        else:
            skipped += 1

    print(f"\nDone — {uploaded} files uploaded, {skipped} skipped.")
    print(f"Location: s3://{config.S3_BUCKET}/unstructured/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="docs", help="Local folder containing docs")
    args = parser.parse_args()
    upload_docs(args.folder)
