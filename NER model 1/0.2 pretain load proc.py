'''
manuel operation
'''
import os
import pandas as pd
from transformers import pipeline


os.chdir('C:/Users/peace/Documents/GitHub/USS/NER model 1')

def read_all_csv(folder_path):
    all_dfs = []
    for f in os.listdir(folder_path):
        if f.lower().endswith('.csv'):
            df = pd.read_csv(os.path.join(folder_path, f))
            df['file'] = f
            all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)

data =  read_all_csv('C:/Users/peace/Documents/GitHub/USS/NER model 1/Generated Assests/') 

# --- 1) Load H2O PII NER (GPU if available) ---
device = 0  # set to -1 for CPU
ner = pipeline(
    task="token-classification",
    model="h2oai/deberta_finetuned_pii",
    aggregation_strategy="simple",
    device=device)

# --- 2) Minimal type normalization (Model A1 only) ---
def norm_type(t: str) -> str:
    t = t.upper()
    if t in {"EMAIL", "E-MAIL"}:
        return "EMAIL"
    if t in {"PHONE", "PHONE_NUMBER", "NUMBER", "TEL"}:
        return "PHONE"
    return t

# Allowed “glue” characters for merges
GLUE = {
    "EMAIL": set("._+-@ \t\r\n"),
    "PHONE": set(" ()-+.\t\r\n"),
}

# --- 3) Merge adjacent same-type spans across glue-only gaps ---
def merge_spans_h2o(spans, text):
    """
    spans: list of dicts from HF pipeline (simple aggregation), each with
           {'start','end','entity_group','score','word', ...}
    returns: new list with EMAIL and PHONE fragments merged
    """
    if not spans:
        return spans[:]

    # sort & normalize types
    items = sorted(spans, key=lambda x: (x["start"], x["end"]))
    for it in items:
        it["_type"] = norm_type(it["entity_group"])

    merged = []
    cur = items[0].copy()

    def trim_span(s, e):
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        return s, e

    for nxt in items[1:]:
        same_type = (nxt["_type"] == cur["_type"])
        can_glue = cur["_type"] in GLUE
        gap = text[cur["end"]:nxt["start"]]

        # Merge rule: same type, gap only contains allowed glue chars
        if same_type and can_glue and all(ch in GLUE[cur["_type"]] for ch in gap):
            cur["end"] = max(cur["end"], nxt["end"])
            cur["word"] = text[cur["start"]:cur["end"]]  # optional: refresh surface
            cur["score"] = max(cur["score"], nxt["score"])  # keep the best confidence
        else:
            # finalize current (trim whitespace)
            s, e = trim_span(cur["start"], cur["end"])
            cur["start"], cur["end"] = s, e
            cur["word"] = text[s:e]
            merged.append(cur)
            cur = nxt.copy()

    # flush last
    s, e = trim_span(cur["start"], cur["end"])
    cur["start"], cur["end"] = s, e
    cur["word"] = text[s:e]
    merged.append(cur)

    # clean helper keys
    for m in merged:
        m.pop("_type", None)
    return merged

# --- 4) Example run ---

text = "Contact Jane Doe at jane.doe@example.com or (617) 555-1234, 12 Main St, Boston MA."
raw_spans = ner(text)
fixed_spans = merge_spans_h2o(raw_spans, text)
print("RAW:")
for s in raw_spans:
    print(f"{s['entity_group']:10s} ({s['start']},{s['end']}) '{text[s['start']:s['end']]}'  score={s['score']:.3f}")

print("\nFIXED:")
for s in fixed_spans:
    print(f"{s['entity_group']:10s} ({s['start']},{s['end']}) '{text[s['start']:s['end']]}'  score={s['score']:.3f}")

# --- 5) Full loop run ---





