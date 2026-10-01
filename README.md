# Citewell

**Ask questions about contracts, leases, loan agreements and financial filings. Every answer is cited to the exact clause, table or page it came from.**

![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.38%2B-FF4B4B.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Citewell is a retrieval-augmented generation (RAG) application for dense, high-stakes documents, where a wrong answer is worse than no answer. It answers only from the documents you give it, says so when the answer is not there, and shows the passage behind every claim so you can check it yourself.

Everything runs locally and for free except the language model call, which uses Groq's free tier.

## Features

- **Cited answers.** Each answer carries numbered citation marks that map to the source passages shown underneath, separated into passages the answer used and passages that were only retrieved.
- **Clause-aware chunking** for legal text. Numbered clauses stay whole instead of being cut mid-sentence by fixed-size splitting.
- **Real table extraction** for financial statements (`pdfplumber`), preserving row and column relationships that flat text extraction destroys.
- **GAAP / Non-GAAP disambiguation.** Headings above tables are detected and appear in citations, so two correct but different figures are not mistaken for a conflict.
- **Bring your own documents.** Upload PDF or Word files and query them in the same session. Nothing is stored.
- **Safe by default.** Uploads are validated (type, size, count, file signature, filename), model output is HTML-escaped, the index is stored as JSON (never pickle), and the model is told to treat document text as data, not instructions.
- **Friendly failures.** Bad PDFs, password-protected files, scanned images, rate limits and bad API keys each produce a specific message, never a traceback.
- **Feedback logging** to SQLite, with the full question, answer, sources and retrieval settings for later analysis.
- **A real evaluation layer.** Retrieval (MRR, Recall@k, Precision@k) and answer faithfulness (LLM-as-judge) are measured against a hand-labelled set.

## Quick start

You need Python 3.11 and a free Groq API key from <https://console.groq.com/keys>.

**Windows (Anaconda Prompt)**

```bat
git clone https://github.com/sami7507/citewell.git
cd citewell

conda create -n citewell python=3.11 -y
conda activate citewell
pip install -r requirements.txt

copy config\.env.example .env
run_app.bat
```

**macOS / Linux**

```bash
git clone https://github.com/sami7507/citewell.git
cd citewell
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp config/.env.example .env
./run_app.sh
```

The app opens at <http://localhost:8501>. You do not have to edit `.env`: if no key is configured, the page asks you to paste one for the session. The first run downloads the embedding model (about 90 MB) and builds the sample index.

> **Sample documents.** Put your PDFs in `storage/sample_docs/` (or run `python scripts/generate_sample_docs.py` to create synthetic ones; it needs `pip install reportlab`).

## Using the app

1. Choose **Sample documents** (a lease, a loan agreement, a 10-K excerpt and financial statements) or **My documents** to upload your own.
2. Ask a question, or click one of the suggested examples.
3. Read the answer. The small numbered marks match the passages under **Sources**, which show exactly what the answer was based on.
4. Mark the answer **Helpful** or **Not helpful**.

## Command line

```bash
python scripts/build_index.py                        # rebuild the sample index
python scripts/cli.py --ask "What is the monthly rent?"
python scripts/run_eval.py                           # retrieval + faithfulness evaluation (uses Groq)
python scripts/run_embedding_comparison.py           # compare embedding models
```

## Project structure

```
citewell/
├── backend/citewell/          # the Python package: all business logic, no UI
│   ├── config.py              # every setting, read from the environment
│   ├── pipeline.py            # ingest -> chunk -> embed -> index, and answer_question()
│   ├── ingestion/             # PDF / DOCX loaders, table extraction
│   ├── chunking/              # clause-aware and recursive chunkers
│   ├── embeddings/            # local sentence-transformers wrapper
│   ├── vectorstore/           # FAISS store with safe JSON persistence
│   ├── retrieval/             # query -> embed -> search -> ranked passages
│   ├── generation/            # grounded prompt, Groq call, error handling
│   ├── services/              # uploads, sample index, secrets bridging
│   ├── storage/               # SQLite feedback database
│   ├── evaluation/            # metrics, faithfulness judge, eval runner, test sets
│   └── utils/                 # rate-limit backoff
├── frontend/                  # Streamlit UI (app.py, theme.py, components.py)
├── storage/                   # sample_docs/, generated index, database, eval reports
├── config/                    # .env.example, secrets.toml.example
├── scripts/                   # CLI, evaluation and sample-data tools
├── tests/                     # 170+ tests
├── .streamlit/config.toml     # Streamlit theme and server settings
├── Dockerfile, requirements*.txt, pytest.ini, .github/workflows/ci.yml
```

The backend never imports Streamlit, and the frontend contains only presentation. The same `pipeline` functions serve the app, the command line, the evaluation harness and the tests.

## Configuration

All settings are environment variables (in `.env`, or Streamlit secrets when deployed). The most useful:

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | none | Free key from console.groq.com |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Language model served by Groq |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model |
| `TOP_K` / `UPLOAD_TOP_K` | `2` / `4` | Passages per answer for samples / uploads |
| `MAX_UPLOAD_FILES`, `MAX_UPLOAD_MB` | `5`, `50` | Upload limits |
| `SAMPLE_DOCS_DIR`, `VECTORSTORE_DIR`, `DATABASE_PATH` | under `storage/` | Where data lives |

See `config/.env.example` for the full list. Changing the embedding model rebuilds the sample index automatically.

## How it works

```
 PDF / DOCX ──► Ingestion ──► Chunking ──► Embedding ──► FAISS index
   pypdf, pdfplumber   clause-aware +     MiniLM (local)   exact cosine
   python-docx         table chunks                              │
                                                                 ▼
 Question ──► embed ──► top-k passages ──► Groq LLM (strict grounding prompt) ──► cited answer
```

More detail, including the design decisions and their trade-offs, is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Evaluation

These figures were measured on the project's hand-labelled set (23 questions across the four sample documents) before the rebuild. The retrieval and chunking logic is unchanged, but the generation prompt gained one extra safety rule, so **re-run `python scripts/run_eval.py` to refresh the faithfulness numbers on your machine.**

| Retrieval (`top_k=2`) | Score |
|---|---|
| MRR | 0.917 |
| Recall@2 | 1.000 |
| Precision@2 | 0.500 |

| Answer faithfulness (LLM-as-judge) | Score |
|---|---|
| Average | 4.83 / 5 |
| Faithful rate | 94.4% (17 of 18 answers) |

`top_k` was tested at 1, 2, 4 and 6; recall and MRR plateau at 2, and higher values only dilute precision. The one flagged answer was a citation mix-up between two adjacent clauses, not a hallucination.

| Embedding model | Dim | MRR | Recall@k | Embed time |
|---|---|---|---|---|
| all-MiniLM-L6-v2 | 384 | 0.891 | 1.000 | 0.63 s |
| all-mpnet-base-v2 | 768 | 0.935 | 1.000 | 3.93 s |

MiniLM is the default: the larger model's small MRR gain did not justify being about 6x slower when both achieve perfect recall.

The labelled set lives in `backend/citewell/evaluation/test_sets/`. The repository ships a small `starter_*.json` placeholder; replace it with your own labels (see the README in that folder).

## Testing

```bash
pip install -r requirements-dev.txt
pytest -m "not integration"      # fast, offline tests
pytest                           # everything, including tests that download models / call the API
```

Tests that need the embedding model or a real `GROQ_API_KEY` are marked `integration`; the live-API tests skip themselves when no key is set.

## Deployment

**Streamlit Community Cloud:** push the repository, set the main file to `frontend/app.py`, and paste `config/secrets.toml.example` (with your real key) into the app's Secrets. Keep `storage/sample_docs/` in the repository.

**Docker:**

```bash
docker build -t citewell .
docker run -p 8501:8501 -e GROQ_API_KEY=your_key citewell
```

## Security and privacy

- Uploaded files are processed in memory and a temporary directory that is deleted immediately; they are never stored.
- A key pasted into the page lives only in that browser session's memory.
- The vector index is JSON plus a FAISS file. Earlier versions used pickle, which can execute code when loaded; old pickle indexes are refused and rebuilt.
- Answers and passages are HTML-escaped before display.
- Retrieved text is passed to the model as untrusted data, with an explicit rule not to follow instructions found inside it.

## Findings from real-world testing

Testing against a real, unmodified 176-page annual report exposed three problems the sample corpus never exercised. Each was traced to its root cause and fixed:

1. **Split currency columns.** The `$` sign sat in its own PDF column, so every figure became two cells. Fixed by detecting and merging columns made up only of currency symbols.
2. **GAAP vs. Non-GAAP tables.** Two identical-looking tables differed only by a heading above each. Fixed by detecting short label-like text above each table and surfacing it in citations (`Table 1 (GAAP), page 24`).
3. **Unit fabrication.** Units ("in thousands") are often stated once elsewhere, so a model can invent a scale word for a bare number. Mitigated with an explicit prompt rule never to invent a scale.

## Known limitations

- **No OCR.** Scanned, image-only PDFs are detected and reported but not read.
- **Prose on table pages.** Pages that contain a table are indexed through the table extraction only, so ordinary text on the same page is not indexed separately.
- **Retrieval can favour prose over tables** when a sentence closely echoes the question. Retrieving more than one passage mitigates it.
- **No reranking stage.** Retrieval is single-pass dense search; a cross-encoder reranker would help on larger corpora.
- **Free-tier storage is ephemeral.** On Streamlit Community Cloud, feedback and the index reset when the app restarts.

## Roadmap

- Cross-encoder reranking
- OCR for scanned documents
- Multi-document comparison questions
- A hosted database for feedback, and promotion of well-rated answers into the evaluation set
- An optional fully local language model backend

## Author

**Sami**

Email: [sami757007@gmail.com](mailto:sami757007@gmail.com)
LinkedIn: [linkedin.com/in/sami7507](https://www.linkedin.com/in/sami7507)

Released under the MIT License.
