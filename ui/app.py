"""
ui/app.py
Streamlit UI — NL input, Plotly charts, S3 doc explorer.
Run from project root:
    streamlit run ui/app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import boto3
import json
import config
from agent.react_agent import query

st.set_page_config(
    page_title = "jay-exer Data Intelligence",
    page_icon  = "🔍",
    layout     = "wide"
)

s3 = boto3.client("s3", region_name=config.AWS_REGION)


# ── helpers ────────────────────────────────────────────────
def auto_chart(df: pd.DataFrame, title: str, chart_type: str) -> go.Figure:
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    selected = chart_type
    if selected == "Auto":
        if cat_cols and num_cols:
            selected = "Bar"
        elif len(num_cols) >= 2:
            selected = "Scatter"
        elif len(df.columns) == 2:
            selected = "Pie"
        else:
            selected = "Table"

    fig = None
    if selected == "Bar" and cat_cols and num_cols:
        fig = px.bar(df, x=cat_cols[0], y=num_cols[0],
                     color=cat_cols[0], title=title,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
    elif selected == "Line" and cat_cols and num_cols:
        fig = px.line(df, x=cat_cols[0], y=num_cols[0],
                      title=title, markers=True)
    elif selected == "Scatter" and len(num_cols) >= 2:
        fig = px.scatter(df, x=num_cols[0], y=num_cols[1],
                         color=cat_cols[0] if cat_cols else None, title=title)
    elif selected == "Pie" and cat_cols and num_cols:
        fig = px.pie(df, names=cat_cols[0], values=num_cols[0], title=title)
    else:
        fig = go.Figure(data=[go.Table(
            header = dict(
                values     = list(df.columns),
                fill_color = "#5DCAA5",
                font       = dict(color="white")
            ),
            cells = dict(values=[df[c] for c in df.columns])
        )])

    if fig:
        fig.update_layout(
            plot_bgcolor  = "rgba(0,0,0,0)",
            paper_bgcolor = "rgba(0,0,0,0)",
            margin        = dict(t=40, b=20, l=20, r=20)
        )
    return fig


def list_s3_docs(prefix: str) -> list[dict]:
    try:
        r = s3.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        return [
            {"key": obj["Key"], "size_kb": round(obj["Size"] / 1024, 1)}
            for obj in r.get("Contents", [])
        ]
    except Exception as e:
        return [{"key": str(e), "size_kb": 0}]


# ── sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 jay-exer")
    st.caption("AWS Bedrock · LlamaIndex · Databricks")
    st.divider()

    chart_type = st.selectbox(
        "Chart type",
        ["Auto", "Bar", "Line", "Scatter", "Pie", "Table"],
        index=0
    )
    st.divider()

    st.markdown("**Data sources**")
    st.markdown("✅ Bedrock Knowledge Base")
    st.markdown("✅ Aurora pgvector (serverless)")
    st.markdown("✅ Databricks jay-exer")
    st.markdown("✅ S3 unstructured docs")
    st.divider()

    with st.expander("📂 S3 Catalog docs"):
        for doc in list_s3_docs("catalog/"):
            st.caption(f"{doc['key']}  ({doc['size_kb']} KB)")

    with st.expander("📂 S3 Unstructured docs"):
        for doc in list_s3_docs("unstructured/"):
            st.caption(f"{doc['key']}  ({doc['size_kb']} KB)")


# ── main chat area ─────────────────────────────────────────
st.header("jay-exer Data Intelligence")
st.caption("Ask questions in plain English — SQL, documents, or both.")

# Example questions
with st.expander("💡 Example questions"):
    examples = [
        "Which territory had the highest revenue last quarter?",
        "Show total invoice amount by region as a chart",
        "What tables contain customer churn data?",
        "List all gold layer tables and their business purpose",
        "Summarize the Q3 risk report from the uploaded documents",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            st.session_state["prefill"] = ex

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("chart") is not None:
            st.plotly_chart(msg["chart"], use_container_width=True)

# Input
prefill  = st.session_state.pop("prefill", "")
question = st.chat_input("Ask anything about your data...") or prefill

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Agent thinking..."):
            result = query(question)

        st.markdown(result["answer"])

        fig = None
        if result.get("sql_data"):
            sql_data = result["sql_data"]
            df = pd.DataFrame(sql_data["rows"], columns=sql_data["columns"])
            if not df.empty:
                fig = auto_chart(df, question, chart_type)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Rows returned: {sql_data.get('row_count', len(df))}")

        st.session_state.messages.append({
            "role":    "assistant",
            "content": result["answer"],
            "chart":   fig
        })
