from __future__ import annotations

import sys
from typing import List, Tuple, Dict, Any


import torch

from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from torch.nn import functional as F
import os


os.chdir('C:/Users/peace/Documents/GitHub/USS/NER model 1')

# -----------------------------
# CUDA / Torch sanity check
# -----------------------------

def torch_cuda_report() -> None:
    print("python exe:", sys.executable)
    print("torch:", torch.__version__)
    print("wheel CUDA:", torch.version.cuda)
    print("cuda.is_available():", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("device:", torch.cuda.get_device_name(0))
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print("VRAM (GB):", round(vram_gb, 2))
torch_cuda_report()

# -----------------------------
# Model loader (GPU)
# -----------------------------

def load_ner_model(model_id: str = "dslim/bert-base-NER"):
    """Load tokenizer + token-classification model on GPU (cuda:0)."""
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForTokenClassification.from_pretrained(model_id).to("cuda").eval()
    return tok, model


# -----------------------------
# Inference mode 1: Aggregated spans
# -----------------------------

def ner_spans(text: str, tok, model) -> List[Dict[str, Any]]:
    """Return clean entity spans using HF pipeline aggregation (on GPU)."""
    ner = pipeline(
        task="token-classification",
        model=model,
        tokenizer=tok,
        device=0,  # cuda:0
        aggregation_strategy="simple",
    )
    return ner(text)


def pretty_print_spans(spans: List[Dict[str, Any]]) -> None:
    if not spans:
        print("<no entities>")
        return
    for p in spans:
        word = p.get("word")
        group = p.get("entity_group")
        score = p.get("score")
        start = p.get("start")
        end = p.get("end")
        print(f"{word:<30}  {group:<10}  score={score:.3f}  span=({start},{end}))")


# -----------------------------
# Inference mode 2: Raw token-level tags (debugging)
# -----------------------------

def ner_token_tags(text: str, tok, model) -> List[Tuple[str, str]]:
    """Return (token, label) for each subword token (no aggregation)."""
    inputs = tok(text, return_tensors="pt", truncation=True, max_length=256).to("cuda")
    with torch.inference_mode():
        logits = model(**inputs).logits  # [1, seq_len, num_labels]
    probs = F.softmax(logits, dim=-1)[0]
    ids = probs.argmax(-1).tolist()
    tokens = tok.convert_ids_to_tokens(inputs["input_ids"][0])
    id2label = model.config.id2label
    return [(t, id2label[i]) for t, i in zip(tokens, ids)]


def pretty_print_token_tags(pairs: List[Tuple[str, str]]) -> None:
    for t, lab in pairs:
        print(f"{t:20} {lab}")


# -----------------------------
# Demo
# -----------------------------

torch_cuda_report()

SAMPLE = "John Doe lives at 123 Main St, Boston, and his SSN is 123-45-6789."
tok, model = load_ner_model("dslim/bert-base-NER")

print("/n=== Aggregated spans (recommended) ===")
spans = ner_spans(SAMPLE, tok, model)
pretty_print_spans(spans)

print("/n=== Raw token-level tags (debugging) ===")
tags = ner_token_tags(SAMPLE, tok, model)
pretty_print_token_tags(tags)



def ner_token_tags_df(text: str, tok, model):
    # Keep offsets on CPU, move tensors to CUDA only for the model
    enc = tok(text, return_tensors="pt", return_offsets_mapping=True, truncation=True, max_length=256)
    enc_cuda = {k: v.to("cuda") for k, v in enc.items() if isinstance(v, torch.Tensor)}
    with torch.inference_mode():
        logits = model(**enc_cuda).logits  # [1, seq_len, num_labels]
    probs = F.softmax(logits, dim=-1)[0]  # [seq_len, num_labels]
    ids = probs.argmax(-1).tolist()
    tokens = tok.convert_ids_to_tokens(enc["input_ids"][0])
    offsets = enc["offset_mapping"][0].tolist()
    id2label = model.config.id2label
    rows = []
    for (tok_str, lab_id, offs, prob_vec) in zip(tokens, ids, offsets, probs):
        start, end = int(offs[0]), int(offs[1])
        conf = float(prob_vec[lab_id].item())
        rows.append({
            "token": tok_str,
            "label": id2label[lab_id],
            "confidence": round(conf, 4),
            "start": start,
            "end": end,
        })
    return pd.DataFrame(rows)

