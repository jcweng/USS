# simple_span_ner_train.py
# Train a new tag (e.g., TRADE_SECRET) from a CSV with columns: text, span
# GPU-friendly on ~8GB VRAM (fp16, small batch)

import re
import pandas as pd
from datasets import Dataset, DatasetDict
from typing import List, Tuple

import numpy as np
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    DataCollatorForTokenClassification,
    TrainingArguments,
    Trainer,
)

# =========================
# CONFIG — edit these
# =========================
CSV_PATH   = "your_data.csv"   # CSV with columns: text, span
TAG_NAME   = "TRADE_SECRET"    # your new label name (e.g., PERCENT, PARTNER_DEAL)
MODEL_ID   = "microsoft/deberta-v3-base"   # good accuracy; you can use "roberta-base" too
MAX_LEN    = 256               # raise if your sentences are long (watch VRAM)
TEST_SPLIT = 0.1               # 10% for dev/test

# =========================
# 1) Load CSV
# =========================
df = pd.read_csv(CSV_PATH)
assert {"text", "span"}.issubset(df.columns), "CSV must have columns: text, span"

# If you have multiple spans per row, separate them by '||'
def parse_spans_field(span_field: str) -> List[str]:
    if pd.isna(span_field) or not str(span_field).strip():
        return []
    return [s.strip() for s in str(span_field).split("||") if s.strip()]

df["spans_list"] = df["span"].apply(parse_spans_field)

# Drop rows that have no spans
df = df[df["spans_list"].map(len) > 0].reset_index(drop=True)

# Build HF dataset
ds_all = Dataset.from_pandas(df[["text", "spans_list"]], preserve_index=False)
ds = ds_all.train_test_split(test_size=TEST_SPLIT, seed=42)
ds = DatasetDict(train=ds["train"], test=ds["test"])

# =========================
# 2) Label schema (BIO)
# =========================
# Single custom tag → 3 classes: O, B-TAG, I-TAG
label_list = ["O", f"B-{TAG_NAME}", f"I-{TAG_NAME}"]
label2id = {l: i for i, l in enumerate(label_list)}
id2label = {i: l for l, i in label2id.items()}

# =========================
# 3) Tokenizer and char→token alignment with offsets
# =========================
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True)

def find_all_occurrences(text: str, phrase: str) -> List[Tuple[int, int]]:
    """Return all (start,end) char spans of 'phrase' in 'text' (case-sensitive)."""
    return [(m.start(), m.end()) for m in re.finditer(re.escape(phrase), text)]

def merge_overlaps(spans: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Merge overlapping/adjacent spans."""
    if not spans:
        return []
    spans = sorted(spans)
    merged = [spans[0]]
    for s, e in spans[1:]:
        ls, le = merged[-1]
        if s <= le:  # overlap or touch
            merged[-1] = (ls, max(le, e))
        else:
            merged.append((s, e))
    return merged

def char_spans_from_row(text: str, phrases: List[str]) -> List[Tuple[int, int, int]]:
    """
    Build entity spans as (start, end, label_id) for all phrases in a row.
    For a single-tag problem, label_id is always B/I handled later at token level;
    here we just carry the (start,end) for the entity region.
    """
    raw_spans = []
    for ph in phrases:
        raw_spans += find_all_occurrences(text, ph)
    raw_spans = merge_overlaps(raw_spans)
    # attach dummy label id (use 1 for B/I region marker; we'll set B/I at tokenization)
    return [(s, e, 1) for (s, e) in raw_spans]

def encode_and_label(example):
    text = example["text"]
    phrases = example["spans_list"]
    ents = char_spans_from_row(text, phrases)  # [(start,end,label_id_placeholder)]

    enc = tokenizer(
        text,
        return_offsets_mapping=True,
        truncation=True,
        max_length=MAX_LEN,
    )
    offsets = enc["offset_mapping"]
    labels = []

    # Build BIO at token level using char offsets
    # - Special tokens have (0,0) offsets → label -100 (ignored in loss)
    # - If a token span lies within any entity char span:
    #     if token.start == entity.start → B
    #     else → I
    for (start_tok, end_tok) in offsets:
        if start_tok == end_tok == 0:
            labels.append(-100)  # special token
            continue

        # Find entity (if any) that covers this token span
        tag = "O"
        for (s_ent, e_ent, _lab) in ents:
            if start_tok >= s_ent and end_tok <= e_ent:  # token fully inside entity
                tag = f"I-{TAG_NAME}"
                if start_tok == s_ent:
                    tag = f"B-{TAG_NAME}"
                break

        labels.append(label2id[tag])

    enc["labels"] = labels
    # Remove offsets to keep batches light
    enc.pop("offset_mapping", None)
    return enc

ds_tokenized = ds.map(encode_and_label, batched=False)

# =========================
# 4) Model & training
# =========================
model = AutoModelForTokenClassification.from_pretrained(
    MODEL_ID,
    num_labels=len(label_list),
    id2label=id2label,
    label2id=label2id,
)

# Collator pads inputs & labels consistently
collator = DataCollatorForTokenClassification(tokenizer)

args = TrainingArguments(
    output_dir=f"./ner_{TAG_NAME.lower()}_{MODEL_ID.split('/')[-1]}",
    learning_rate=3e-5,
    per_device_train_batch_size=8,     # fits on ~8GB with fp16
    per_device_eval_batch_size=16,
    gradient_accumulation_steps=1,
    num_train_epochs=5,
    weight_decay=0.01,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    logging_steps=50,
    fp16=True,
    gradient_checkpointing=True,
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=ds_tokenized["train"],
    eval_dataset=ds_tokenized["test"],
    tokenizer=tokenizer,
    data_collator=collator,
)

trainer.train()
