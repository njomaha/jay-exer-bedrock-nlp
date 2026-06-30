# jay-exer Bedrock NLP Intelligence Platform

AWS Bedrock · LlamaIndex ReActAgent · Aurora pgvector · Databricks jay-exer · Streamlit + Plotly

> **Folder location:** `C:\Users\nj_ra\.aws\jay-exer-bedrock-nlp`
> Sits alongside your other AWS exercises under `.aws\`:
> ```
> C:\Users\nj_ra\.aws\
> ├── bedrock-rag\              ← your existing S3 Vectors RAG project
> └── jay-exer-bedrock-nlp\    ← this project
> ```

---

## What This Does

- Ask questions in plain English about your jay-exer Databricks tables
- Agent searches Unity Catalog metadata → generates SQL → runs it → charts results
- Also searches unstructured S3 docs (PDFs, reports, JSON) via hybrid RAG
- Built on AWS Bedrock (Titan Embed v2 + Claude Sonnet) — no external vector DB

---

## Project Structure

```
jay-exer-bedrock-nlp/
├── config.py                      # central config — reads .env
├── .env                           # your credentials (never commit this)
├── requirements.txt
├── setup_aurora.py                # one-time: create Aurora pgvector cluster
├── ingestion/
│   ├── extract_catalog.py         # Unity Catalog metadata → S3
│   ├── upload_unstructured.py     # local docs → S3
│   ├── create_kb.py               # one-time: create Bedrock KB
│   └── refresh_catalog.py         # scheduled re-sync
├── agent/
│   ├── tools.py                   # catalog_search, unstructured_search, run_sql
│   └── react_agent.py             # ReActAgent + Claude via Bedrock
├── eval/
│   └── ragas_hooks.py             # Ragas faithfulness + relevancy scoring
├── ui/
│   └── app.py                     # Streamlit UI + Plotly charts
└── docs/                          # drop your PDFs/JSON/text files here
```

---

## Setup — PowerShell (Windows)

### Step 1 — Create folder and venv

```powershell
mkdir C:\Users\nj_ra\.aws\jay-exer-bedrock-nlp
cd C:\Users\nj_ra\.aws\jay-exer-bedrock-nlp
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If you get a permissions error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 2 — Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 3 — Edit .env

```powershell
notepad .env
```

Fill in your Databricks HOST, HTTP_PATH, TOKEN.
Leave KB_ID and Aurora ARNs blank for now — the setup scripts will fill them.

### Step 4 — Create S3 bucket

```powershell
aws s3 mb s3://jay-exer-catalog-rag --region us-east-1
```

### Step 5 — Create Aurora pgvector (one-time, ~5 min)

```powershell
python setup_aurora.py
```

Copy the two ARNs printed at the end into your .env file.

### Step 6 — Create IAM role for Bedrock KB

```powershell
aws iam create-role --role-name BedrockKBRole --assume-role-policy-document '{
  "Version":"2012-10-17",
  "Statement":[{
    "Effect":"Allow",
    "Principal":{"Service":"bedrock.amazonaws.com"},
    "Action":"sts:AssumeRole"
  }]
}'
aws iam attach-role-policy --role-name BedrockKBRole --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam attach-role-policy --role-name BedrockKBRole --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
aws iam attach-role-policy --role-name BedrockKBRole --policy-arn arn:aws:iam::aws:policy/AmazonRDSDataFullAccess
```

### Step 7 — Upload catalog metadata to S3

```powershell
python ingestion/extract_catalog.py
```

### Step 8 — Upload your unstructured docs

Drop PDFs, JSON, txt files into the `docs/` folder then:
```powershell
python ingestion/upload_unstructured.py
```

### Step 9 — Create Bedrock Knowledge Base (one-time)

```powershell
python ingestion/create_kb.py
```

Copy the KB_ID and DS IDs into your .env file.

### Step 10 — Run the UI

```powershell
streamlit run ui/app.py
```

Opens at http://localhost:8501

---

## Day-to-Day Usage

| Task | Command |
|---|---|
| Refresh catalog after schema changes | `python ingestion/refresh_catalog.py` |
| Add new docs | Drop into `docs/` → `python ingestion/upload_unstructured.py` |
| Run eval regression | `python eval/ragas_hooks.py` |
| Start UI | `streamlit run ui/app.py` |

---

## Estimated Monthly Cost (dev / light use)

| Component | Cost |
|---|---|
| Aurora pgvector serverless (0.5 ACU idle) | ~$25 |
| Titan Embed v2 queries | ~$6 |
| Claude Sonnet via Bedrock (~500 queries/day) | ~$45 |
| S3 storage | ~$5 |
| **Total** | **~$80/month** |

Significantly cheaper than Databricks Vector Search endpoint (~$200-400/month idle).

---

## LinkedIn Project Description

> **AWS Bedrock NLP-to-SQL Intelligence Platform** — Production-grade natural language data interface built on AWS Bedrock, LlamaIndex ReActAgent, Aurora pgvector (serverless), Titan Embed v2, and Claude Sonnet. Supports structured SQL queries against Databricks Unity Catalog and unstructured S3 document search (PDFs, reports, JSON) via hybrid RAG (dense + BM25). Streamlit UI with auto-rendered Plotly charts. Ragas eval hooks for faithfulness and context precision scoring. GitHub: `njomaha/jay-exer-bedrock-nlp`
