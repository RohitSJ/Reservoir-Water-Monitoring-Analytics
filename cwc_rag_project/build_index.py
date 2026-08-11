import argparse
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2" 


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="./data")
    args = ap.parse_args()

    datadir = Path(args.datadir)
    with open(datadir / "chunks.json", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"[build_index] loading model {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)

    texts = [f"Section: {c['section']}\n{c['text']}" for c in chunks]
    print(f"[build_index] embedding {len(texts)} chunks ...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.array(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim) 
    index.add(embeddings)

    faiss.write_index(index, str(datadir / "chunks.index"))
    with open(datadir / "chunks_meta.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"[build_index] wrote {datadir/'chunks.index'} ({index.ntotal} vectors, dim={dim})")


if __name__ == "__main__":
    main()
