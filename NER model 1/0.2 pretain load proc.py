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
        gap_len = nxt["start"] - cur["end"]
        if same_type and gap_len == 0:
            cur["end"] = max(cur["end"], nxt["end"])
            cur["word"] = text[cur["start"]:cur["end"]]
            cur["score"] = max(cur["score"], nxt["score"])
        else:
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


# --- 4) smale sample run ---
text = "Post-operatively, support was inadequate. This requiring ongoing therapy (SSN: 696082539). Significant complications arose. From Jackson."
text = "Patient Shirly Lamax the device failed while, unexpected bleeding occurred. Normal function returned. (SSN: 345-77-1432)."
text = "The patient, Cruz, after activation, the system shut down. Leading to procedure termination. From McLean, MD."
raw_spans = ner(text)
fixed_spans = merge_spans_h2o(raw_spans, text)


# --- 4b) Show token-level candidates (no aggregation) ---
ner_tokens = pipeline(
    task="token-classification",
    model="h2oai/deberta_finetuned_pii",
    aggregation_strategy=None,   # <-- important: raw token-level predictions
    device=device
)
raw_tokens = ner_tokens(text)
print("\nALL TOKEN-LEVEL ENTITIES (unaggregated):")
for t in raw_tokens:
    print(f"{t['entity']:15s} ({t['start']},{t['end']}) "
          f"'{text[t['start']:t['end']]}' score={t['score']:.3f}")


print("RAW:")
for s in raw_spans:
    print(f"{s['entity_group']:10s} ({s['start']},{s['end']}) '{text[s['start']:s['end']]}'  score={s['score']:.3f}")

print("\nFIXED:")
for s in fixed_spans:
    print(f"{s['entity_group']:10s} ({s['start']},{s['end']}) '{text[s['start']:s['end']]}'  score={s['score']:.3f}")


# --- 6) Batched redaction (compat mode) ---
from tqdm import tqdm
MAX_LEN = 384
BATCH_SIZE = 16
CHUNK = 512

# Configure tokenizer once for older pipeline APIs
ner.tokenizer.model_max_length = MAX_LEN
ner.tokenizer.truncation_side = "right"
ner.tokenizer.padding_side = "right"

def redact_from_entities(text, ents):
    fixed = merge_spans_h2o(ents, text)
    repls = []
    for s in fixed:
        label = norm_type(s.get("entity_group", "PII"))
        tag = f"(({label}))"
        repls.append((s["start"], s["end"], tag))
    for start, end, tag in sorted(repls, key=lambda x: x[0], reverse=True):
        text = text[:start] + tag + text[end:]
    return text

def batched_redact(texts):
    # No truncation/padding/max_length kwargs here — handled by tokenizer config
    all_out = ner(texts, batch_size=BATCH_SIZE)
    return [redact_from_entities(t, ents) for t, ents in zip(texts, all_out)]

data_redacted = data.copy()
texts = data_redacted["text"].astype(str).tolist()

out = []
for i in tqdm(range(0, len(texts), CHUNK), desc="Redacting"):
    chunk = texts[i:i+CHUNK]
    out.extend(batched_redact(chunk))

data_redacted["pii-treated"] = out
data_redacted.to_csv("pii_treated_dataset.csv", index=False)



