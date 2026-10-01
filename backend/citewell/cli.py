"""
Command-line interface for Citewell: build the index and ask questions with no
UI. Useful for verifying the pipeline end to end.

    python scripts/cli.py --build
    python scripts/cli.py --ask "What is the monthly rent?"
    python scripts/cli.py                      # interactive loop
"""

import argparse
import sys

from citewell import config
from citewell.embeddings.embedder import Embedder
from citewell.generation.generator import GenerationError, Generator
from citewell.pipeline import answer_question, build_index
from citewell.retrieval.retriever import Retriever


def print_answer(question: str, result) -> None:
    print(f"\nQ: {question}\nA: {result.answer}")
    if result.sources_used:
        print("\nSources:")
        for source in result.sources_used:
            print(f"  - {source}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Citewell CLI")
    parser.add_argument("--build", action="store_true", help="(Re)build the index from the sample documents")
    parser.add_argument("--ask", type=str, help="Ask a single question and exit")
    parser.add_argument("--top-k", type=int, default=None, help="Number of passages to retrieve")
    args = parser.parse_args()

    config.configure_logging()
    config.ensure_dirs()

    if args.build:
        build_index()
        if not args.ask:
            return

    try:
        embedder = Embedder()
        retriever = Retriever.from_saved_store(embedder=embedder)
    except FileNotFoundError:
        print("No index found. Run with --build first: python scripts/cli.py --build")
        sys.exit(1)

    try:
        generator = Generator()
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    def ask(question: str) -> None:
        try:
            print_answer(question, answer_question(question, retriever=retriever, generator=generator, top_k=args.top_k))
        except GenerationError as exc:
            print(f"\nError: {exc}\n")

    if args.ask:
        ask(args.ask)
        return

    print("Citewell CLI. Ask about the sample documents (Ctrl+C or 'exit' to quit).")
    while True:
        try:
            question = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break
        if question.lower() in ("exit", "quit"):
            break
        if question:
            ask(question)


if __name__ == "__main__":
    main()
