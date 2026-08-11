"""
ingest.py — STEP 1 of the RAG pipeline
----------------------------------------
Takes a CWC "Weekly Bulletin on Live Storage Status of Reservoirs" PDF
(the format published every Thursday on the CWC website) and produces:

  1. reservoirs.db   -> SQLite table `reservoirs` with ONE ROW PER RESERVOIR
                        (exact numbers: FRL, live capacity, current storage,
                        last year storage, normal storage, % values, etc.)
                        This is used for STRUCTURED / EXACT-NUMBER questions
                        like "what is the current storage of Almatti?"

  2. chunks.json     -> Page-wise text chunks (Brief Note, Table-01, basin-wise
                        report, region-wise narrative, IMD rainfall section...)
                        This is used for SEMANTIC / NARRATIVE questions like
                        "which region has better storage than normal?"

Run:
    python3 ingest.py /path/to/bulletin.pdf --outdir ./data
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

import pdfplumber

STATES = [
    "Himachal Pradesh", "Punjab", "Rajasthan", "Assam", "Bihar", "Jharkhand",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Tripura", "West Bengal",
    "Goa", "Gujrat", "Gujarat", "Maharashtra", "Chattisgarh", "Chhattisgarh",
    "Madhya Pradesh", "Uttar Pradesh", "Uttarakhand", "Andhra Pradesh",
    "Karnataka", "Kerala", "Tamil Nadu", "Telangana",
]
# sort longest first so "Madhya Pradesh" matches before "Pradesh" false positives etc.
STATES_SORTED = sorted(STATES, key=len, reverse=True)

MERGED_FLOAT_RE = re.compile(r"^(\d{1,4}\.\d{3})(\d{1,4}\.\d{3})$")
TEXT_FLOAT_RE = re.compile(r"^([A-Za-z]+)(\d{1,4}\.\d{3})$")
FLOAT_RE = re.compile(r"^\d{1,4}\.\d{2,3}$")
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def split_merged_floats(tokens):
    """Some numbers get glued together by pdfplumber e.g. '300.9900.000'
    -> split into '300.990' and '0.000'."""
    out = []
    for t in tokens:
        m = MERGED_FLOAT_RE.match(t)
        if m:
            out.append(m.group(1))
            out.append(m.group(2))
        else:
            out.append(t)
    return out


def split_text_float(tokens):
    """Split tokens like 'Maharashtra0.000' -> 'Maharashtra', '0.000'."""
    out = []
    for t in tokens:
        m = TEXT_FLOAT_RE.match(t)
        if m:
            out.append(m.group(1))
            out.append(m.group(2))
        else:
            out.append(t)
    return out


def parse_reservoir_row(words_row):
    """words_row: list of word strings for one row of the main 166-reservoir table."""
    if not words_row or not words_row[0].isdigit():
        return None

    sr_no = words_row[0]
    rest = split_text_float(words_row[1:])

    # find the date token -> everything between name/state block and date
    date_idx = None
    for i, t in enumerate(rest):
        if DATE_RE.match(t):
            date_idx = i
            break
    if date_idx is None:
        return None

    name_state_tokens = rest[:date_idx]
    numeric_after_name = rest[date_idx + 1:]  # values AFTER the date
    # values before date (within name_state_tokens) include 2 numeric benefit fields
    # at the END of name_state_tokens (IRR_CCA, HYDEL_MW), then FRL, LIVE_CAP just before date
    # Identify trailing numeric tokens in name_state_tokens
    nums_before_date = []
    while name_state_tokens and (FLOAT_RE.match(name_state_tokens[-1]) or
                                  MERGED_FLOAT_RE.match(name_state_tokens[-1])):
        nums_before_date.insert(0, name_state_tokens.pop())
    nums_before_date = split_merged_floats(nums_before_date)

    if len(nums_before_date) < 4:
        return None
    irr_cca, hydel_mw, frl, live_cap = nums_before_date[-4:]

    # remaining name_state_tokens = reservoir name words + state name words
    text_blob = " ".join(name_state_tokens)
    state = None
    for s in STATES_SORTED:
        if text_blob.endswith(s):
            state = s
            text_blob = text_blob[: -len(s)].strip()
            break
    name = text_blob.strip() if text_blob else " ".join(name_state_tokens)

    nums_after_date = split_merged_floats(numeric_after_name)
    if len(nums_after_date) < 9:
        return None
    (this_level, this_storage, this_year_pct,
     last_level, last_storage, last_year_pct,
     normal_storage, normal_pct,
     pct_to_last, pct_to_normal) = (nums_after_date + [None] * 10)[:10]

    def f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    return {
        "sr_no": int(sr_no),
        "name": name,
        "state": state,
        "irr_cca_th_ha": f(irr_cca),
        "hydel_mw": f(hydel_mw),
        "frl_m": f(frl),
        "live_cap_frl_bcm": f(live_cap),
        "this_level_m": f(this_level),
        "this_storage_bcm": f(this_storage),
        "this_year_pct_of_frl": f(this_year_pct),
        "last_level_m": f(last_level),
        "last_storage_bcm": f(last_storage),
        "last_year_pct_of_frl": f(last_year_pct),
        "normal_storage_bcm": f(normal_storage),
        "normal_pct_of_frl": f(normal_pct),
        "pct_this_to_last_year": f(pct_to_last),
        "pct_this_to_normal": f(pct_to_normal),
    }


def extract_reservoir_rows(pdf):
    records = []
    for page in pdf.pages:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        if not words:
            continue
        rows = {}
        for w in words:
            key = round(w["top"])
            rows.setdefault(key, []).append(w)
        keys = sorted(rows.keys())
        line_token_lists = []
        for k in keys:
            row = sorted(rows[k], key=lambda w: w["x0"])
            toks = [w["text"] for w in row]
            # sr_no sometimes glued to reservoir name e.g. '131SOM' -> '131','SOM'
            if toks:
                m = re.match(r"^(\d{1,3})([A-Z].+)$", toks[0])
                if m:
                    toks = [m.group(1), m.group(2)] + toks[1:]
            line_token_lists.append(toks)

        # Sequentially merge wrapped continuation lines (e.g. a state name or
        # reservoir name that wraps onto the next line, like "LOWER" / "BHAWANI")
        # into the row that started with a serial number.
        buffer = []
        name_extra = []  # wrapped continuation words of the reservoir name

        for toks in line_token_lists:
            if toks and toks[0].isdigit() and len(toks) > 3:
                # looks like the start of a new reservoir row
                if buffer:
                    rec = parse_reservoir_row(buffer)
                    if rec:
                        if name_extra:
                            rec["name"] = (rec["name"] + " " + " ".join(name_extra)).strip()
                        records.append(rec)
                buffer = list(toks)
                name_extra = []
            else:
                if buffer and toks and all(t.isalpha() for t in toks):
                    # a wrapped continuation word of the reservoir name/state
                    # (e.g. 'SAGARA', 'BHAWANI') -> append to reservoir name afterwards
                    name_extra.extend(toks)
                elif buffer:
                    buffer.extend(toks)
                # else: header/junk line before any data row started -> ignore
        if buffer:
            rec = parse_reservoir_row(buffer)
            if rec:
                if name_extra:
                    rec["name"] = (rec["name"] + " " + " ".join(name_extra)).strip()
                records.append(rec)
    # de-duplicate by (sr_no, name) keeping first occurrence, drop obviously bad rows
    seen = set()
    clean = []
    for r in records:
        key = (r["sr_no"], r["name"])
        if key in seen:
            continue
        if r["live_cap_frl_bcm"] is None:
            continue
        seen.add(key)
        clean.append(r)
    clean.sort(key=lambda r: r["sr_no"])
    return clean


def extract_text_chunks(pdf, bulletin_date):
    """Page-level text chunks for semantic search, with light section labeling."""
    chunks = []
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if not text:
            continue
        # Skip pure reservoir-data-table pages from the *narrative* index —
        # they're already captured in structured form. Heuristic: page has
        # many numeric-heavy short lines AND the '166 IMPORTANT RESERVOIRS'
        # header => treat as table page, still keep a short chunk in case
        # user asks something the structured parser missed.
        section = "General"
        header_match = re.search(
            r"(BRIEF NOTE|STORAGE STATUS OF|TABLE-0\d[^\n]*|WEEKLY REPORT[^\n]*"
            r"|IMD SUB-DIVISIONS[^\n]*|Map Indicating[^\n]*)",
            text,
        )
        if header_match:
            section = header_match.group(1).strip()

        chunks.append({ 
            "id": f"page-{i+1}",
            "page": i + 1,
            "section": section,
            "bulletin_date": bulletin_date,
            "text": text,
        })
    return chunks


def guess_bulletin_date(pdf):
    for page in pdf.pages[:2]:
        text = page.extract_text() or ""
        m = re.search(r"AS ON (\d{2}\.\d{2}\.\d{4})", text.upper())
        if m:
            return m.group(1)
    return "unknown"


def save_to_sqlite(records, db_path, bulletin_date):
    db_path = Path(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reservoirs (
            bulletin_date TEXT,
            sr_no INTEGER,
            name TEXT,
            state TEXT,
            irr_cca_th_ha REAL,
            hydel_mw REAL,
            frl_m REAL,
            live_cap_frl_bcm REAL,
            this_level_m REAL,
            this_storage_bcm REAL,
            this_year_pct_of_frl REAL,
            last_level_m REAL,
            last_storage_bcm REAL,
            last_year_pct_of_frl REAL,
            normal_storage_bcm REAL,
            normal_pct_of_frl REAL,
            pct_this_to_last_year REAL,
            pct_this_to_normal REAL,
            PRIMARY KEY (bulletin_date, name)
        )
    """)
    for r in records:
        cur.execute("""
            INSERT OR REPLACE INTO reservoirs VALUES
            (:bulletin_date, :sr_no, :name, :state, :irr_cca_th_ha, :hydel_mw,
             :frl_m, :live_cap_frl_bcm, :this_level_m, :this_storage_bcm,
             :this_year_pct_of_frl, :last_level_m, :last_storage_bcm,
             :last_year_pct_of_frl, :normal_storage_bcm, :normal_pct_of_frl,
             :pct_this_to_last_year, :pct_this_to_normal)
        """, {**r, "bulletin_date": bulletin_date})
    conn.commit()
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("--outdir", default="./data")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(args.pdf_path) as pdf:
        bulletin_date = guess_bulletin_date(pdf)
        print(f"[ingest] bulletin date detected: {bulletin_date}")

        records = extract_reservoir_rows(pdf)
        print(f"[ingest] structured reservoir rows extracted: {len(records)}")

        chunks = extract_text_chunks(pdf, bulletin_date)
        print(f"[ingest] text chunks extracted: {len(chunks)}")

    save_to_sqlite(records, outdir / "reservoirs.db", bulletin_date)
    with open(outdir / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    with open(outdir / f"reservoirs_{bulletin_date}.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"[ingest] wrote {outdir/'reservoirs.db'}")
    print(f"[ingest] wrote {outdir/'chunks.json'}")


if __name__ == "__main__":
    sys.exit(main())
