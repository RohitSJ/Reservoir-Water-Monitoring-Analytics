import argparse
import json
import os
import re
import sqlite3
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 5


class CWCRag:
    def __init__(self, datadir="./data"):
        self.datadir = Path(datadir)
        self.conn = sqlite3.connect(self.datadir / "reservoirs.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        with open(self.datadir / "chunks_meta.json", encoding="utf-8") as f:
            self.chunks = json.load(f)
        self.index = faiss.read_index(str(self.datadir / "chunks.index"))
        self.model = SentenceTransformer(MODEL_NAME)

        cur = self.conn.execute("SELECT DISTINCT name FROM reservoirs")
        self.reservoir_names = [r["name"] for r in cur.fetchall()]

    # ---------- A) STRUCTURED / EXACT LOOKUP ----------
    def find_reservoir_in_query(self, query):
        q_upper = query.upper()
        # exact / substring match against known reservoir names (longest first
        # so 'LOWER BHAWANI' matches before a shorter false positive)
        candidates = sorted(self.reservoir_names, key=len, reverse=True)
        for name in candidates:
            if name in q_upper:
                return name
        return None

    def structured_lookup(self, name):
        cur = self.conn.execute(
            "SELECT * FROM reservoirs WHERE name = ? ORDER BY bulletin_date DESC LIMIT 1",
            (name,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # ---------- B) SEMANTIC SEARCH ----------
    def semantic_search(self, query, top_k=TOP_K):
        qvec = self.model.encode([query], normalize_embeddings=True)
        qvec = np.array(qvec, dtype="float32")
        scores, idxs = self.index.search(qvec, top_k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append({**self.chunks[idx], "score": float(score)})
        return results

    # ---------- GENERATION ----------
    def build_prompt(self, query, structured_row=None, chunks=None):
        context_parts = []
        if structured_row:
            context_parts.append(
                "STRUCTURED RESERVOIR RECORD (exact figures from CWC bulletin dated "
                f"{structured_row['bulletin_date']}):\n" + json.dumps(structured_row, indent=2)
            )
        if chunks:
            for c in chunks:
                context_parts.append(
                    f"[Page {c['page']} | {c['section']}]\n{c['text'][:1800]}"
                )
        context = "\n\n---\n\n".join(context_parts)
        prompt = (
            "You are answering questions about a Central Water Commission (CWC) "
            "weekly reservoir storage bulletin. Answer the user's question using "
            "ONLY the CONTEXT below. Cite BCM (billion cubic metres) and % figures "
            "exactly as given. If the context does not contain the answer, say so "
            "clearly instead of guessing.\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {query}\n\nANSWER:"
        )
        return prompt

    def call_llm(self, prompt):
        """Calls Groq's free LLM API. Requires GROQ_API_KEY env var."""
        import requests

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return ("[GROQ_API_KEY not set — showing retrieved context instead]\n\n" + prompt)

        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 600,
            },
        )
        data = resp.json()
        if "error" in data:
            return f"[Groq API error: {data['error']}]"
        return data["choices"][0]["message"]["content"]

    def ask(self, query):
        reservoir_name = self.find_reservoir_in_query(query)
        structured_row = self.structured_lookup(reservoir_name) if reservoir_name else None

        # still do semantic search too, for extra context (e.g. state/region trend)
        chunks = self.semantic_search(query, top_k=3 if structured_row else TOP_K)

        prompt = self.build_prompt(query, structured_row=structured_row, chunks=chunks)
        answer = self.call_llm(prompt)
        return {
            "answer": answer,
            "structured_row": structured_row,
            "chunks_used": [{"page": c["page"], "section": c["section"], "score": c["score"]} for c in chunks],
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="./data")
    args = ap.parse_args()

    rag = CWCRag(args.datadir)
    print("CWC Reservoir Bulletin RAG — type a question (or 'exit')")
    while True:
        q = input("\n> ").strip()
        if q.lower() in ("exit", "quit"):
            break
        result = rag.ask(q)
        print("\n" + result["answer"])
        print("\n[retrieved:", result["chunks_used"], "]")


if __name__ == "__main__":
    main()
