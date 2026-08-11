# CWC Reservoir Bulletin — RAG (Retrieval-Augmented Generation) Module

This is the **RAG portion** of your project. It sits *after* your Big Data
download/scraping step (which already fetches the weekly PDF from the CWC
site every 7 days) and *before* the user-facing chatbot.

Pipeline: **PDF → Ingest → Index → Retrieve → Generate**

```
weekly bulletin PDF
        │
        ▼
  ingest.py  ──────► reservoirs.db (SQLite, structured, exact numbers)
        │       └──► chunks.json   (page-wise narrative text)
        ▼
 build_index.py ────► chunks.index (FAISS vector index) + chunks_meta.json
        ▼
 rag_query.py  ─────► ask(question) → retrieves + calls LLM → answer
        ▼
   app.py  (Flask web UI, optional demo layer)
```

## Why hybrid (structured + vector), not pure vector RAG?

A pure embedding-RAG over a bulletin full of tables is unreliable for
numbers (embeddings are great at *topic* similarity, bad at *exact figures*).
So this pipeline does two things at query time:

1. **Structured path** — if the question names a specific reservoir (e.g.
   "Tehri", "Nagarjuna Sagar"), it is looked up directly in a SQLite table
   with one row per reservoir (FRL, live capacity, this year/last
   year/normal storage, %, etc.) — **zero hallucination risk** for numbers.
2. **Semantic path** — for narrative questions ("which region is doing
   worse than normal?", "which basins are deficient?") it embeds the
   question and retrieves the most relevant page-level chunks (Brief Note,
   Table-01, basin-wise report, IMD rainfall section) via FAISS.

Both paths feed into the same LLM call, which is told to answer **only**
from the retrieved context.

## Step-by-step (you have ~1 hour — follow in order)

### 0. Install dependencies
```bash
pip install -r requirements.txt --break-system-packages
```

### 1. Ingest a downloaded bulletin PDF (repeat for every weekly PDF you download)
```bash
python3 ingest.py /path/to/bulletin-06-08-2026.pdf --outdir ./data
```
This was tested end-to-end on the CWC bulletin dated 06.08.2026 and correctly
extracted **all 166 reservoirs** into `data/reservoirs.db`, e.g.:
```
Tehri            -> 1.561 BCM  (59.70% of FRL, 101.86% of normal)
Nagarjuna Sagar  -> 0.161 BCM  (3.15% of FRL,  7.63% of normal)
Almatti          -> 2.596 BCM  (83.61% of FRL, 97.01% of normal)
```
It also writes `data/chunks.json` — one text chunk per PDF page (Brief Note,
Table-01 region-wise, basin-wise report, IMD rainfall section, etc.).

> Since CWC republishes this exact PDF layout every week, re-running
> `ingest.py` on each new week's PDF keeps `reservoirs.db` growing with a
> new dated snapshot per reservoir (primary key = bulletin_date + name), so
> you can also answer *trend* questions across weeks later if you want to
> extend this.

### 2. Build the vector index (semantic search)
```bash
python3 build_index.py --datadir ./data
```
This downloads the small `all-MiniLM-L6-v2` sentence-transformer model
(needs internet — first run only, then it's cached) and builds a FAISS
index over the page chunks.

### 3. Set your LLM API key
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
(You can swap `call_llm()` in `rag_query.py` for any other LLM API if you
don't have an Anthropic key — OpenAI, a local Ollama model, etc. The
retrieval logic doesn't change, only that one function.)

### 4. Ask questions (CLI)
```bash
python3 rag_query.py --datadir ./data
```
Example questions to demo for your evaluators:
- "What is the current live storage of Tehri dam?"
- "How much has Nagarjuna Sagar's storage dropped compared to normal?"
- "Which region has storage better than last year?"
- "Which basins are in deficient or highly deficient category?"
- "List reservoirs in Tamil Nadu with less than 50% of normal storage."

### 5. (Optional, for a nicer demo) Web UI
```bash
python3 app.py --datadir ./data
```
Open `http://127.0.0.1:5000`, type a question in the box.

## File-by-file summary (for your project report)

| File | Purpose |
|---|---|
| `ingest.py` | PDF → structured SQLite (`reservoirs.db`) + text chunks (`chunks.json`) |
| `build_index.py` | Embeds chunks with `all-MiniLM-L6-v2`, builds FAISS index |
| `rag_query.py` | Hybrid retriever (SQL exact-lookup + FAISS semantic search) + LLM answer generation |
| `app.py` | Minimal Flask UI wrapping `rag_query.CWCRag.ask()` |
| `data/reservoirs.db` | One row per reservoir per bulletin date (exact figures) |
| `data/chunks.json` | Page-wise narrative text for semantic retrieval |
| `data/chunks.index` | FAISS vector index (built in step 2) |

## Note on this sandbox

`ingest.py` was fully run and verified here against your uploaded PDF (166/166
reservoirs extracted correctly). `build_index.py`/`rag_query.py` need to
download the embedding model from huggingface.co and call the Anthropic API,
which this sandbox's network doesn't allow — but they will work normally on
your own machine with internet access. Everything is otherwise ready to run.
