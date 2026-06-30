"""
eval/ragas_hooks.py
Ragas evaluation hooks for answer faithfulness, relevancy, and context precision.
Run after any significant change to the agent or KB.

Usage:
    python eval/ragas_hooks.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness, context_precision
from datasets import Dataset
from agent.tools import catalog_search, unstructured_search
from agent.react_agent import query

# Golden test set — add more as your catalog grows
GOLDEN_QUESTIONS = [
    "Which territory had the highest revenue last quarter?",
    "What tables contain customer data in the silver layer?",
    "What columns are available in the gold layer for reporting?",
    "Show me total invoice amount by region",
]


def eval_single(question: str) -> dict:
    """Run one question through the agent and score it with Ragas."""
    cat_results  = json.loads(catalog_search(question))
    uns_results  = json.loads(unstructured_search(question))

    contexts = []
    if isinstance(cat_results, list):
        contexts += [r["content"] for r in cat_results if "content" in r]
    if isinstance(uns_results, list):
        contexts += [r["content"] for r in uns_results if "content" in r]

    result = query(question)
    answer = result["answer"]

    data = Dataset.from_dict({
        "question": [question],
        "answer":   [answer],
        "contexts": [contexts]
    })

    scores = evaluate(
        data,
        metrics=[answer_relevancy, faithfulness, context_precision]
    )
    return {
        "question":         question,
        "answer_relevancy": round(scores["answer_relevancy"], 3),
        "faithfulness":     round(scores["faithfulness"], 3),
        "context_precision":round(scores["context_precision"], 3)
    }


def run_regression():
    print("Running Ragas regression eval...\n")
    results = []
    for q in GOLDEN_QUESTIONS:
        print(f"Q: {q}")
        scores = eval_single(q)
        results.append(scores)
        print(f"  Relevancy:   {scores['answer_relevancy']}")
        print(f"  Faithfulness:{scores['faithfulness']}")
        print(f"  Precision:   {scores['context_precision']}\n")

    avg_rel  = sum(r["answer_relevancy"]  for r in results) / len(results)
    avg_fai  = sum(r["faithfulness"]      for r in results) / len(results)
    avg_pre  = sum(r["context_precision"] for r in results) / len(results)

    print("── Averages ─────────────────────────")
    print(f"  Relevancy:    {avg_rel:.3f}")
    print(f"  Faithfulness: {avg_fai:.3f}")
    print(f"  Precision:    {avg_pre:.3f}")
    print("─────────────────────────────────────")
    return results


if __name__ == "__main__":
    run_regression()
