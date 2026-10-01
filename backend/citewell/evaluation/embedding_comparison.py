"""
Embedding model comparison for Citewell.

Embeds the SAME chunks under each candidate model and measures retrieval
quality (against the labelled eval set) and embedding speed side by side, so
the choice of default model rests on measurements rather than convention.

Run:  python scripts/run_embedding_comparison.py
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from citewell import config
from citewell.embeddings.embedder import Embedder
from citewell.evaluation.metrics import evaluate_retrieval
from citewell.evaluation.test_sets_loader import load_all_test_sets
from citewell.pipeline import load_and_chunk_documents
from citewell.retrieval.retriever import Retriever
from citewell.vectorstore.store import VectorStore

DEFAULT_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
]


@dataclass
class ModelComparisonResult:
    model_name: str
    embedding_dim: int
    num_chunks: int
    embed_time_seconds: float
    chunks_per_second: float
    mrr: float
    recall_at_k: float
    precision_at_k: float
    top_k: int


def compare_embedding_models(
    model_names: Optional[List[str]] = None, top_k: Optional[int] = None
) -> List[ModelComparisonResult]:
    """Embed identical chunks with each model and measure speed and retrieval quality."""
    model_names = model_names or DEFAULT_MODELS
    top_k = top_k or config.TOP_K

    chunks = load_and_chunk_documents(verbose=False)  # loaded once so every model sees identical chunks
    items = load_all_test_sets()
    texts = [c.text for c in chunks]

    results: List[ModelComparisonResult] = []
    for model_name in model_names:
        embedder = Embedder(model_name)

        start = time.time()
        embeddings = embedder.embed_texts(texts)
        embed_time = time.time() - start

        store = VectorStore(embedding_dim=embedder.embedding_dim, embedding_model=model_name)
        store.add(chunks, embeddings)
        retriever = Retriever(embedder=embedder, vectorstore=store)
        report = evaluate_retrieval(retriever, items, top_k=top_k)

        results.append(
            ModelComparisonResult(
                model_name=model_name,
                embedding_dim=embedder.embedding_dim,
                num_chunks=len(chunks),
                embed_time_seconds=embed_time,
                chunks_per_second=(len(chunks) / embed_time) if embed_time > 0 else float("inf"),
                mrr=report.mrr,
                recall_at_k=report.recall_at_k,
                precision_at_k=report.precision_at_k,
                top_k=top_k,
            )
        )
    return results


def print_comparison(results: List[ModelComparisonResult]) -> None:
    """Print a side-by-side table and a one-line summary of the first two models."""
    print("=" * 78)
    print("Embedding model comparison")
    print("=" * 78)
    print(f"{'Model':<42}{'Dim':>5}{'MRR':>8}{'Recall':>8}{'Embed s':>9}{'Chunks/s':>10}")
    for r in results:
        short = r.model_name.split("/")[-1]
        print(f"{short:<42}{r.embedding_dim:>5}{r.mrr:>8.3f}{r.recall_at_k:>8.3f}"
              f"{r.embed_time_seconds:>9.2f}{r.chunks_per_second:>10.1f}")

    if len(results) >= 2:
        a, b = results[0], results[1]
        a_name, b_name = a.model_name.split("/")[-1], b.model_name.split("/")[-1]
        slower = (b.embed_time_seconds / a.embed_time_seconds) if a.embed_time_seconds > 0 else float("nan")
        print()
        print(f"{a_name} vs {b_name}: MRR {a.mrr:.3f} vs {b.mrr:.3f} "
              f"(difference {b.mrr - a.mrr:+.3f}), {b_name} embeds {slower:.1f}x slower.")
    print("=" * 78)


def save_comparison(results: List[ModelComparisonResult], path: Optional[Path] = None) -> Path:
    """Save the comparison as JSON and return the path written."""
    path = Path(path or (config.EVAL_RESULTS_DIR / "embedding_comparison.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([asdict(r) for r in results], handle, indent=2)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare embedding models on the labelled eval set")
    parser.add_argument("--models", nargs="+", default=None, help="Model ids to compare")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    results = compare_embedding_models(model_names=args.models, top_k=args.top_k)
    print_comparison(results)
    print(f"\nSaved to: {save_comparison(results, Path(args.output) if args.output else None)}")


if __name__ == "__main__":
    main()
