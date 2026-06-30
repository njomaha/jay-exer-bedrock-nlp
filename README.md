# jay-exer Bedrock NLP Intelligence Platform

> **Ask plain-English questions. Get grounded answers from your lakehouse and documents.**

A production-grade agentic RAG system built on AWS Bedrock that routes natural language questions across two retrieval paths — structured SQL queries against a Unity Catalog lakehouse and semantic search over unstructured PDF documents — through a single conversational Streamlit UI with auto-generated Plotly charts.

![Architecture](https://img.shields.io/badge/AWS-Bedrock-orange?logo=amazonaws)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-ReActAgent-blue)
![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red?logo=streamlit)

---

## What It Does

Ask "Which territory had the highest revenue last quarter?" and the agent retrieves the answer from an ingested shareholder letter PDF. Ask "What is the average customer balance by region?" and it finds the right table in the lakehouse catalog, checks the real column values, generates SQL, and returns a bar chart — all from the same chat input.

The agent **never guesses table or column names**. Every answer is grounded in retrieved metadata or document content, not LLM training data.

---

## Architecture

```
Natural Language Question
        │
        ▼
┌─────────────────────────────────────────────────┐
│           LlamaIndex ReActAgent                  │
│           (Claude Sonnet via Bedrock)            │
└────────┬────────────────────────┬───────────────┘
         │                        │
         ▼                        ▼
┌────────────────┐      ┌──────────────────────┐
│ catalog_search │      │ unstructured_search   │
│                │      │                       │
│ Structured     │      │ PDF / Document RAG    │
│ metadata from  │      │ Shareholder letters,  │
│ Unity Catalog  │      │ reports, policies     │
│ (34 tables)    │      │                       │
└───────┬────────┘      └──────────┬────────────┘
        │                          │
        ▼                          │
┌────────────────┐                 │
│ get_column_    │                 │
│ samples        │                 │
│ (real values   │                 │
│ for filters)   │                 │
└───────┬────────┘                 │
        │                          │
        ▼                          │
┌────────────────┐                 │
│ run_sql        │                 │
│ (Databricks    │                 │
│ SQL Warehouse) │                 │
└───────┬────────┘                 │
        │                          │
        └──────────┬───────────────┘
                   ▼
        ┌─────────────────────┐
        │  Streamlit UI       │
        │  + Plotly Charts    │
        └─────────────────────┘
```

### Vector Store

Both pipelines land in **Aurora PostgreSQL Serverless v2 with pgvector**, using hybrid retrieval:
- **Dense** — Titan Embed v2 (1024-dim) vector similarity via HNSW index
- **Keyword** — PostgreSQL full-text search via GIN index

This matters because pure semantic search misses exact term matches — `ssn` should find the `ssn` column literally, not just semantically adjacent content.

---

## Two Ingestion Pipelines

### 1. Structured — Unity Catalog Metadata
Extracts table names, column names, types, business descriptions, and live sample values from all catalog tables. Each table becomes a rich text document that acts as the agent's schema map — refreshable on a schedule as the schema evolves.

### 2. Unstructured — PDF / Document Pipeline
PDFs uploaded to S3 are chunked using **Bedrock's native semantic chunking** (coherent passage splits, not fixed-size token windows), embedded with Titan Embed v2, and indexed in the same Aurora pgvector table alongside the catalog metadata.

---

## Project Structure

```
jay-exer-bedrock-nlp/
├── config.py                      # Central config — reads .env
├── .env.example                   # Template — copy to .env and fill in
├── requirements.txt
├── setup_aurora.py                # One-time: create Aurora pgvector cluster
├── ingestion/
│   ├── extract_catalog.py         # Unity Catalog metadata → S3
│   ├── upload_unstructured.py     # Local docs → S3
│   ├── create_kb.py               # One-time: create Bedrock Knowledge Base
│   └── refresh_catalog.py         # Scheduled re-sync on schema changes
├── agent/
│   ├── tools.py                   # catalog_search, unstructured_search, run_sql
│   └── react_agent.py             # ReActAgent + Claude via Bedrock
├── eval/
│   └── ragas_hooks.py             # Ragas faithfulness + relevancy scoring
├── ui/
│   └── app.py                     # Streamlit UI + Plotly auto-charts
└── docs/                          # Drop PDFs here → upload_unstructured.py
```

---

## Setup

### Prerequisites
- AWS account with Bedrock model access (Claude Sonnet, Titan Embed v2)
- AWS CLI v2.15+ installed and configured
- Python 3.11+
- Databricks workspace with Unity Catalog

### Step 1 — Clone and install

```bash
git clone https://github.com/njomaha/jay-exer-bedrock-nlp.git
cd jay-exer-bedrock-nlp
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 2 — Configure

```bash
cp .env.example .env
# Edit .env with your actual values
```

### Step 3 — Create S3 bucket

```bash
aws s3 mb s3://your-bucket-name --region us-east-1
```

### Step 4 — Create Aurora pgvector (one-time, ~5 min)

```bash
python setup_aurora.py
# Copy the ARNs printed at the end into .env
```

Then create the required table and indexes:

```bash
# Run these three commands against your Aurora cluster via AWS CLI or console
# 1. Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

# 2. Create table (1024 dims = Titan Embed v2)
CREATE TABLE bedrock_kb (
    id        uuid PRIMARY KEY,
    embedding vector(1024),
    text      text,
    metadata  json
);

# 3. GIN index for keyword search (required by Bedrock KB)
CREATE INDEX bedrock_kb_text_idx
    ON bedrock_kb USING gin (to_tsvector('simple', text));

# 4. HNSW index for vector search (required by Bedrock KB)
CREATE INDEX bedrock_kb_embedding_idx
    ON bedrock_kb USING hnsw (embedding vector_cosine_ops);
```

### Step 5 — Create IAM role for Bedrock KB

```bash
# Create trust policy file
echo '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"bedrock.amazonaws.com"},"Action":"sts:AssumeRole"}]}' > trust.json

aws iam create-role --role-name BedrockKBRole --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name BedrockKBRole --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam attach-role-policy --role-name BedrockKBRole --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
aws iam attach-role-policy --role-name BedrockKBRole --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess
aws iam attach-role-policy --role-name BedrockKBRole --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

### Step 6 — Ingest data

```bash
# Extract Unity Catalog metadata → S3
python ingestion/extract_catalog.py

# Upload PDFs from docs/ folder → S3
python ingestion/upload_unstructured.py

# Create Bedrock Knowledge Base (one-time)
python ingestion/create_kb.py
# Copy KB_ID and DS IDs printed at the end into .env
```

### Step 7 — Trigger ingestion jobs

```bash
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_CATALOG_DS_ID

aws bedrock-agent start-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_UNSTRUCTURED_DS_ID
```

### Step 8 — Launch the UI

```bash
streamlit run ui/app.py
```

Opens at `http://localhost:8501`

---

## Day-to-Day Usage

| Task | Command |
|---|---|
| Refresh catalog after schema changes | `python ingestion/refresh_catalog.py` |
| Add new PDF docs | Drop into `docs/` → `python ingestion/upload_unstructured.py` |
| Run eval regression | `python eval/ragas_hooks.py` |
| Start UI | `streamlit run ui/app.py` |

---

## Example Questions

| Question | Path |
|---|---|
| "What tables contain customer data?" | catalog_search |
| "What is average balance by region?" | catalog_search → run_sql → chart |
| "Which territory had highest revenue last quarter?" | unstructured_search → PDF |
| "Summarize the Q3 shareholder letter" | unstructured_search → PDF |
| "List all gold layer tables" | catalog_search |

---

## Estimated Monthly Cost (dev / light use)

| Component | Cost |
|---|---|
| Aurora pgvector serverless (0.5 ACU idle) | ~$25 |
| Titan Embed v2 queries | ~$6 |
| Claude Sonnet via Bedrock (~500 queries/day) | ~$45 |
| S3 storage | ~$5 |
| **Total** | **~$80/month** |

Significantly cheaper than always-on managed vector search endpoints (~$200–400/month idle).

---

## Stack

| Layer | Technology |
|---|---|
| LLM | Claude Sonnet via AWS Bedrock |
| Embeddings | Amazon Titan Embed v2 (1024-dim) |
| Vector store | Aurora PostgreSQL Serverless v2 + pgvector |
| Retrieval | Hybrid: HNSW dense + GIN keyword |
| Agent | LlamaIndex ReActAgent |
| Chunking | Bedrock native semantic chunking |
| Structured data | Unity Catalog lakehouse |
| UI | Streamlit + Plotly |
| Eval | Ragas (faithfulness, relevancy, context precision) |

---

## Author

**Jayaraman Iyer Narayanan** — Principal Data & AI Architect
[LinkedIn](https://linkedin.com/in/jayaraman-iyernarayanan-34514920) · [GitHub](https://github.com/njomaha)
