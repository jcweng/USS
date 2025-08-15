
"""
PDF_PII_redactor_v11_noui.py
--------------------------------
Streamlit-free redaction module exposing a CLI and Python API.

What it does
- Loads spaCy (tries multiple models) and attaches an EntityRuler with patterns
- Optional spell-check (SymSpell) and grammar (LanguageTool)
- Builds auto NLP spans with skip rules
- Merges user-provided tags (B4/B6/Other) with NLP redactions; user tags win on overlap
- Updates AcroForm fields in the PDF and writes a final redacted PDF

Dependencies (pip):
  pip install spacy pymupdf symspellpy language-tool-python

CLI usage:
  python PDF_PII_redactor_v11_noui.py input.pdf --out out.pdf
  python PDF_PII_redactor_v11_noui.py input.pdf --out out.pdf --tags tags.json
  python PDF_PII_redactor_v11_noui.py ./docs --outdir ./results --batch --tags tags.json

User tags JSON (optional):
{
  "by_field_name": {
    "PatientName": [{"text":"Alice","type":"B6","label":"patient info"}]
  },
  "by_page": {
    "1": [{"text":"Formula-XYZ","type":"B4","label":"trade secret"}]
  },
  "global": [
    {"text":"acetaminophen","type":"B4","label":"trade secret"}
  ]
}

Notes:
- If both by_field_name and by_page/global apply, they are combined for that field.
- If LanguageTool server isn't available, grammar correction is skipped gracefully.
"""

from __future__ import annotations
import io, json, re, sys, argparse, hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import fitz  # PyMuPDF

# ---------------- NLP setup ----------------

MODELS_TO_TRY = ["en_core_web_trf", "en_core_web_lg", "en_core_web_md", "en_core_web_sm"]

# Minimal example patterns; extend as needed
ENTITY_RULER_PATTERNS: List[Dict[str, Any]] = [
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}-\d{2}-\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}$"}}, {"TEXT":"-"}, {"TEXT": {"REGEX": r"^\d{2}$"}}, {"TEXT":"-"}, {"TEXT": {"REGEX": r"^\d{4}$"}}]},
    {"label": "DATE", "pattern": [{"IS_DIGIT": True}, {"LOWER": {"REGEX":"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"}}, {"IS_DIGIT": True}]},
    # Simplified address-like pattern (number + words + state + zip)
    {"label": "ADDRESS", "pattern": [{"TEXT": {"REGEX": r"^\d{3,6}$"}}, {"IS_ALPHA": True, "OP":"+"}, {"IS_ALPHA": True, "OP":"?"},
                                     {"IS_ALPHA": True, "OP":"+"}, {"IS_PUNCT": True, "OP":"?"},
                                     {"IS_ALPHA": True, "LENGTH": 2}, {"IS_PUNCT": True, "OP":"?"},
                                     {"IS_DIGIT": True, "LENGTH": 5}]},
]

def load_nlp(models: List[str] = None):
    import spacy
    from spacy.pipeline import EntityRuler
    models = models or MODELS_TO_TRY
    last_err = None
    for m in models:
        try:
            nlp = spacy.load(m, disable=["lemmatizer"])
            ruler = nlp.add_pipe("entity_ruler", before="ner") if "ner" in nlp.pipe_names else nlp.add_pipe("entity_ruler")
            ruler.add_patterns(ENTITY_RULER_PATTERNS)
            return nlp, m
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Failed to load any spaCy model {models}: {last_err}")

# ---------------- Spell & Grammar (optional) ----------------

def build_symspell(max_edit_distance: int = 2, prefix_length: int = 7):
    try:
        from symspellpy import SymSpell, Verbosity
        sym = SymSpell(max_edit_distance, prefix_length)
        # A default frequency dictionary path; adjust if you store it elsewhere
        from symspellpy import pkg_resources
        freq_path = pkg_resources.resource_filename("symspellpy", "frequency_dictionary_en_82_765.txt")
        sym.load_dictionary(freq_path, term_index=0, count_index=1)
        return sym
    except Exception:
        return None

def apply_spelling(sym, text: str) -> str:
    if not sym:
        return text
    try:
        # conservative correction: space-separated terms
        from symspellpy import Verbosity
        out_words = []
        for tok in re.split(r"(\s+)", text):
            if not tok or tok.isspace():
                out_words.append(tok)
                continue
            sugg = sym.lookup(tok, Verbosity.CLOSEST, max_edit_distance=2, include_unknown=True)
            out_words.append(sugg[0].term if sugg else tok)
        return "".join(out_words)
    except Exception:
        return text

def build_grammarlang(lang: str = "en-US"):
    try:
        import language_tool_python as lt
        return lt.LanguageTool(lang)
    except Exception:
        return None

def apply_grammar(tool, text: str) -> str:
    if not tool:
        return text
    try:
        return tool.correct(text)
    except Exception:
        return text

# ---------------- Redaction helpers ----------------

USER_LABELS = {"B4": "trade secret", "B6": "patient info", "OTHER": "redacted"}
SKIP_LABELS = {"CARDINAL", "QUANTITY", "PERCENT"}

def build_auto_spans(doc) -> List[Tuple[int,int,str]]:
    # Your skip rules from the Streamlit code
    spans = []
    for ent in doc.ents:
        if ent.label_ in SKIP_LABELS:
            continue
        if ent.label_ in {"FAC", "GPE"} and any(e.label_ == "ADDRESS" for e in doc.ents):
            continue
        if ent.label_ == "PERSON" and any(ch.isdigit() for ch in ent.text):
            continue
        if ent.label_ == "DATE" and not re.search(r"(19|20)\d{2}", ent.text):
            continue
        spans.append((ent.start_char, ent.end_char, f"[{ent.label_}]"))
    return spans

def merge_redactions(text: str, auto_spans: List[Tuple[int,int,str]], user_tags: List[Dict[str,Any]]) -> str:
    spans: List[Dict[str, Any]] = []
    # auto (lower priority)
    for s,e,repl in auto_spans:
        spans.append({"start":s,"end":e,"repl":repl,"prio":1})
    # user (higher priority)
    for t in user_tags or []:
        patt = re.escape(t["text"])
        ttype = (t.get("type") or "TAG").upper()
        lbl   = t.get("label") or USER_LABELS.get(ttype, "redacted")
        repl  = f"[{ttype} - {lbl}]"
        for m in re.finditer(patt, text):
            spans.append({"start":m.start(),"end":m.end(),"repl":repl,"prio":2})
    if not spans:
        return text
    spans.sort(key=lambda s: (s["start"], -s["prio"], -(s["end"]-s["start"])))
    merged, cur_end = [], -1
    for s in spans:
        if s["start"] >= cur_end:
            merged.append(s); cur_end = s["end"]
        else:
            last = merged[-1]
            if (s["prio"] > last["prio"]) or (s["prio"] == last["prio"] and (s["end"]-s["start"]) > (last["end"]-last["start"])):
                merged[-1] = s; cur_end = s["end"]
    out, pos = [], 0
    for s in merged:
        out.append(text[pos:s["start"]]); out.append(s["repl"]); pos = s["end"]
    out.append(text[pos:])
    return "".join(out)

def _tags_for_field(user_tags: Dict[str, Any], field_name: str, page_index: int) -> List[Dict[str,Any]]:
    user_tags = user_tags or {}
    out: List[Dict[str,Any]] = []
    # by_field_name
    by_field = (user_tags.get("by_field_name") or {}).get(field_name, [])
    out.extend(by_field)
    # by_page
    page_list = (user_tags.get("by_page") or {}).get(str(page_index+1), [])
    out.extend(page_list)
    # global
    out.extend(user_tags.get("global", []))
    return out

# ---------------- Core processing ----------------

def redact_full_pdf_bytes(
    input_pdf: Path,
    nlp=None,
    sym=None,
    lt_tool=None,
    user_tags: Optional[Dict[str,Any]] = None
) -> Tuple[bytes, Dict[str, Any]]:
    """Returns (final_pdf_bytes, audit_dict)."""
    if nlp is None:
        nlp, model_name = load_nlp()
    else:
        model_name = getattr(nlp, "meta", {}).get("name", "custom")

    doc = fitz.open(input_pdf)
    updated = 0
    auto_count = 0
    user_count = 0

    # Iterate AcroForm fields; if none, no-op (you can extend to text redaction via redaction annots)
    for page_index in range(doc.page_count):
        page = doc[page_index]
        widgets = page.widgets() or []
        for w in widgets:
            text = w.field_value or ""
            if not text or not isinstance(text, str):
                continue

            # optional normalization passes
            text2 = apply_spelling(sym, text)
            text2 = apply_grammar(lt_tool, text2)

            # NLP + entity ruler
            doc_ent = nlp(text2)
            auto_spans = build_auto_spans(doc_ent)
            auto_count += len(auto_spans)

            # User tags for this field/page
            tags = _tags_for_field(user_tags, w.field_name, page_index)
            user_count += len(tags or [])

            redacted = merge_redactions(text2, auto_spans, tags)

            if redacted != text:
                w.field_value = redacted
                w.update()
                updated += 1

    # Save to bytes
    out_buf = io.BytesIO()
    doc.save(out_buf)
    doc.close()

    audit = {
        "nlp_model": model_name,
        "entities_auto_spans": auto_count,
        "user_tags_count": user_count,
        "fields_updated": updated,
        "pages": doc.page_count if doc else None
    }
    return out_buf.getvalue(), audit

# ---------------- CLI ----------------

def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Run redaction (NLP+user tags) without Streamlit.")
    ap.add_argument("input", help="PDF path or directory of PDFs")
    ap.add_argument("--out", help="Output PDF path (single-file mode)")
    ap.add_argument("--outdir", help="Output directory (batch mode)")
    ap.add_argument("--batch", action="store_true", help="Treat input as directory and process all PDFs")
    ap.add_argument("--tags", help="Path to optional user tags JSON")
    ap.add_argument("--no-spell", action="store_true")
    ap.add_argument("--no-grammar", action="store_true")
    args = ap.parse_args()

    # Load optional user tags
    user_tags = None
    if args.tags:
        user_tags = json.loads(Path(args.tags).read_text(encoding="utf-8"))

    # Build engines once
    nlp, model_name = load_nlp()
    sym = None if args.no_spell else build_symspell()
    lt_tool = None if args.no_grammar else build_grammarlang()

    in_path = Path(args.input)
    if args.batch or in_path.is_dir():
        outdir = Path(args.outdir or "./results")
        outdir.mkdir(parents=True, exist_ok=True)
        results = []
        for pdf in sorted(in_path.glob("*.pdf")):
            data, audit = redact_full_pdf_bytes(pdf, nlp=nlp, sym=sym, lt_tool=lt_tool, user_tags=user_tags)
            out_pdf = outdir / f"{pdf.stem}.redacted.pdf"
            out_pdf.write_bytes(data)
            results.append({
                "file": str(pdf),
                "out": str(out_pdf),
                "sha256": _sha256(out_pdf),
                "audit": audit
            })
        print(json.dumps({"model": model_name, "count": len(results), "results": results}, indent=2))
    else:
        if not args.out:
            raise SystemExit("--out is required for single-file mode")
        data, audit = redact_full_pdf_bytes(in_path, nlp=nlp, sym=sym, lt_tool=lt_tool, user_tags=user_tags)
        Path(args.out).write_bytes(data)
        print(json.dumps({"model": model_name, "out": args.out, "audit": audit}, indent=2))

if __name__ == "__main__":
    main()
