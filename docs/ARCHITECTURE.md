# Architecture and design decisions

## Layers

| Layer | Package | Responsibility |
|---|---|---|
| Presentation | `frontend/` | Streamlit pages, theme, HTML helpers. No business logic. |
| Services | `citewell.services` | Upload validation and indexing, sample-index lifecycle, secrets bridging. |
| Core pipeline | `citewell.pipeline` and the stage packages | Ingest, chunk, embed, index, retrieve, generate. |
| Storage | `citewell.vectorstore`, `citewell.storage` | FAISS index (JSON + binary) and the SQLite feedback database. |
| Evaluation | `citewell.evaluation` | Metrics, faithfulness judge, runner, labelled test sets. |

Dependencies point one way: frontend -> services -> pipeline stages -> config. The backend has no Streamlit import, so every piece is testable on its own.

## Key decisions

**Clause-aware chunking.** Legal clauses are self-contained units. Fixed-size splitting cuts them mid-sentence and produces chunks that are useless or misleading alone. Numbered headers are detected with a conservative regex; long clauses fall back to recursive splitting, and pages with no clauses fall back entirely.

**Tables as markdown chunks with captions.** `pdfplumber` detects real grid structure; each table becomes one markdown chunk, prefixed with a caption listing its line items (embedding models match prose far better than pipe-delimited grids) and any detected heading.

**Table pages are excluded from prose chunking.** `pypdf` flattens a table into a jumbled cell-by-cell dump; indexing it next to the clean table chunk would put a garbled duplicate in competition with the correct one.

**Exact search.** Embeddings are L2-normalised, so inner product is cosine similarity and `IndexFlatIP` is exact. At this corpus size approximate search would add risk for no gain.

**Strict grounding prompt.** The model must answer only from the supplied passages, cite each fact as `(Source N)`, say so when the answer is missing, never invent a unit, and treat document text as data. Citation labels are built into the context before the model sees it, which is far more reliable than inferring provenance afterwards.

**Separate `top_k` for uploads.** `TOP_K=2` is measured on a 24-chunk corpus; an arbitrary long upload needs more passages, so uploads default to 4 with a light relevance floor.

**JSON, not pickle.** Loading a pickle executes code. The index stores chunks as JSON, writes files atomically, records the embedding model in a manifest, and cross-checks vector and chunk counts on load. A mismatch or an old pickle index triggers a rebuild rather than trust.

**Failures are first-class.** Loaders raise `DocumentLoadError`, uploads raise `UploadError`, generation raises `GenerationError`, each with a message written for the person using the app. Rate limits are retried using the wait time Groq suggests.

## Request flow

1. The user asks a question; the UI trims and length-limits it.
2. The retriever embeds it and searches FAISS for the top passages (with a relevance floor for uploads).
3. The generator builds a labelled context, calls Groq with retry/backoff, and returns the answer plus the source labels.
4. The UI turns `(Source N)` into numbered marks and shows the passages, split into used and merely retrieved.
5. Optional feedback is stored in SQLite with the full context.
