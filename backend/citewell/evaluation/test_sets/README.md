# Evaluation test sets

`starter_*.json` is a small placeholder set (18 questions) written from the sample documents so the
test suite and evaluation runner work out of the box.

To use your own hand-labelled set, copy your JSON files into this folder and **delete the `starter_*.json`
files** (item ids must be unique across all files). Each item needs: `id`, `question`, `expected_answer`,
`expected_source_doc`, `expected_clause_number` (or `null` for documents without numbered clauses) and
`expected_keywords` (single words or numbers are safest, since PDF line wrapping can split phrases).
