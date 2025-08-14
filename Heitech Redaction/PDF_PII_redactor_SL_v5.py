# PDF_PII_redactor_SL_v4-3.py

import os
from dotenv import load_dotenv
import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import spacy
import io
import re
from streamlit_pdf_viewer import pdf_viewer
from spacy.pipeline import EntityRuler
from spacy import displacy

# Env & API setup
os.chdir(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(".env")
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Setup SymSpell
from symspellpy.symspellpy import SymSpell, Verbosity

dictionary_path = os.path.join(os.path.dirname(__file__), "frequency_dictionary_en_82_765.txt")
sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1):
    st.error("⚠️ SymSpell dictionary failed to load.")
    st.stop()

# Page config
st.set_page_config(layout="wide")
if "doc_cache" not in st.session_state:
    st.session_state["doc_cache"] = {}

if "correction_cache" not in st.session_state:
    st.session_state["correction_cache"] = {}

st.title("📑 PDF PII Redactor with Manual Highlight")

# Clear uploaded file
if st.sidebar.button("❌ Clear Uploaded PDF"):
    st.session_state.pop("uploaded_file", None)
    st.experimental_rerun()

# Sidebar navigation
page_mode = st.sidebar.radio("📂 Navigation", ["📥 Upload PDF", "🔒 Auto Redact", "🖍️ Manual Highlights", " 📦 Fallback Engine"])

PATTERNS = [
    {"label": "ADDRESS", "pattern": [{"TEXT": {"REGEX": r"^\d{3,6}$"}}, {"IS_ALPHA": True, "OP": "+"}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True, "OP": "+"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_PUNCT": True, "OP": "?"}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "ADDRESS", "pattern": [{"IS_DIGIT": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "DATE", "pattern": [{"IS_DIGIT": True}, {"LOWER": {"REGEX": "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"}}, {"IS_DIGIT": True}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}-\d{2}-\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}$"}}, {"TEXT": "-"}, {"TEXT": {"REGEX": r"^\d{2}$"}}, {"TEXT": "-"}, {"TEXT": {"REGEX": r"^\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^(ssn|ss|social|security)[:]?$", "flags": "i"}}, {"TEXT": {"REGEX": r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"}}]},
    {"label": "SSN", "pattern": [
    {"TEXT": {"REGEX": r"^(ssn|ss|social|security)[:]?$", "flags": "i"}},
    {"TEXT": {"REGEX": r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"}}
    ]}
]

# Cached NLP loader
@st.cache_resource
def load_nlp():
    nlp = spacy.load("en_core_web_trf")
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    ruler.add_patterns(PATTERNS)
    return nlp

nlp = load_nlp()

PII_COLORS = {"ADDRESS": "lightblue", "DATE": "lightpink", "SSN": "orange"}

# Correction engine
@st.cache_data(show_spinner=False)
def apply_text_corrections(text, spell_level, grammar_level, fluency_level):
    if spell_level == grammar_level == fluency_level == "disable":
        return text

    # OpenAI once
    if "3" in (spell_level, grammar_level, fluency_level):
        instructions = []
        if spell_level == "3":
            instructions.append("fix spelling")
        if grammar_level == "3":
            instructions.append("correct grammar")
        if fluency_level == "3":
            instructions.append("rewrite for clarity and fluency")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant. Please {' and '.join(instructions)}."},
                {"role": "user", "content": text}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()

    corrected_text = text

    # Spelling
    if spell_level == "2":
        corrected_text = " ".join([
            sym_spell.lookup(w, Verbosity.CLOSEST, max_edit_distance=2)[0].term
            if sym_spell.lookup(w, Verbosity.CLOSEST, max_edit_distance=2) else w
            for w in corrected_text.split()
        ])

    # Grammar
    if grammar_level == "1":
        import language_tool_python
        tool = language_tool_python.LanguageTool("en-US")
        matches = tool.check(corrected_text)
        corrected_text = language_tool_python.utils.correct(corrected_text, matches)

    # Fluency placeholder
    if fluency_level == "1":
        corrected_text = corrected_text

    return corrected_text

# Upload section
if "uploaded_file" not in st.session_state:
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded:
        st.session_state.uploaded_file = uploaded
    else:
        st.stop()
else:
    uploaded = st.session_state.uploaded_file
    st.markdown(f"**✅ Using uploaded file:** {uploaded.name}")

# Upload tab UI
if page_mode == "📥 Upload PDF":
    col1, col2 = st.columns(2)
    with col1:
        spell_level = st.selectbox(
            "Spelling Correction", ["disable", "1", "2", "3"],
            index=["disable", "1", "2", "3"].index(st.session_state.get("spell_level", "disable"))
        )
    with col2:
        grammar_level = st.selectbox(
            "Grammar Correction", ["disable", "1", "3"],
            index=["disable", "1", "2", "3"].index(st.session_state.get("grammar_level", "disable"))
        )

    fluency_level = st.selectbox(
        "Fluency Correction", ["disable", "1", "2", "3"],
        index=["disable", "1", "2", "3"].index(st.session_state.get("fluency_level", "disable"))
    )
    sample_text = st.text_area("Paste some sample text to preview correction:", "The quick brown fox jumpps ovver the lazi dog.", height=150)

    def correct_text_preview(text, s, g, f):
        return apply_text_corrections(text, s, g, f)

    if st.button("✅ Run Preview on Sample Text"):
        corrected = correct_text_preview(sample_text, spell_level, grammar_level, fluency_level)
        st.text_area("🔧 Corrected Text", corrected, height=150)

    if st.button("✅ Apply Selection to Main Document"):
        st.session_state["spell_level"] = spell_level
        st.session_state["grammar_level"] = grammar_level
        st.session_state["fluency_level"] = fluency_level
        st.session_state["doc_cache"] = {}
        st.session_state["correction_cache"] = {}
        st.success("Correction levels saved. Proceed to redaction.")

# After upload
binary_data = uploaded.getvalue()
doc = fitz.open(stream=binary_data, filetype="pdf")

text_correction_levels = (
    st.session_state.get("spell_level", "disable"),
    st.session_state.get("grammar_level", "disable"),
    st.session_state.get("fluency_level", "disable"))

st.session_state["full_text"] = "".join([p.get_text() for p in doc])

# Redaction target pages
widgets_df = []
pii_table = []
output_buffer = io.BytesIO()

def correct_field_text(val):
    norm = re.sub(r"\s+", " ", val.replace("\n", " ").strip())
    key = (norm, text_correction_levels)
    if key in st.session_state["correction_cache"]:
        return st.session_state["correction_cache"][key]
    corrected = apply_text_corrections(norm, *text_correction_levels)
    st.session_state["correction_cache"][key] = corrected
    return corrected


if page_mode == "🔒 Auto Redact":
    for page_num, page in enumerate(doc):
        widgets = page.widgets()
        if not widgets:
            continue

        for widget in widgets:
            fname = widget.field_name
            val = widget.field_value
            if not val or widget.field_type != fitz.PDF_WIDGET_TYPE_TEXT:
                continue

            if (page_num == 1 and fname == "advEvDescribe") or \
               (page_num == 4 and fname.startswith("cProdName")) or \
               (page_num == 6 and fname == "addNarr"):

                display_name = None
                if page_num == 1:
                    display_name = "B5"
                elif page_num == 4:
                    suffix = fname.replace("cProdName", "")
                    display_name = f"D10-{suffix}"
                elif page_num == 6:
                    display_name = "H11"

                corrected = correct_field_text(val)
                doc_cache_key = (page_num, fname)
                if doc_cache_key in st.session_state["doc_cache"]:
                    doc_ent = st.session_state["doc_cache"][doc_cache_key]
                else:
                    doc_ent = nlp(corrected)
                    st.session_state["doc_cache"][doc_cache_key] = doc_ent
                redacted = corrected

                for ent in doc_ent.ents:
                    if ent.label_ in {"CARDINAL", "QUANTITY", "PERCENT"}:
                        continue
                    if ent.label_ in {"FAC", "GPE"} and any(e.label_ == "ADDRESS" for e in doc_ent.ents):
                        continue
                    if ent.label_ == "PERSON" and any(char.isdigit() for char in ent.text):
                        continue
                    if ent.label_ == "DATE" and not re.search(r"(19|20)\d{2}", ent.text):
                        continue  # Only redact if actual date string
                    redacted = redacted.replace(
                        ent.text,
                        f"[{ent.label_}]{' ' * max(0, len(ent.text) - len(ent.label_) - 2)}"
                    )

                pii_table.append({
                    "Page": page_num + 1,
                    "Field Name": fname,
                    "input": corrected,
                    "output": redacted,
                    "Display Name": display_name
                })

                widget.field_value = redacted
                widget.update()

                widgets_df.append({
                    "Page": page_num + 1,
                    "Field Name": fname,
                    "Field Value": corrected,
                    "Display Name": display_name
                })

    doc.save(output_buffer)
    doc.close()
    st.session_state["widgets_df"] = pd.DataFrame(widgets_df)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📄 Full PDF Text")
        pdf_viewer(binary_data, width=900, height=900, key="original")
    with col2:
        st.subheader("📄 Redacted PDF Preview")
        pdf_viewer(output_buffer.getvalue(), width=900, height=900, key="redacted")

    st.download_button("⬇️ Download Redacted PDF", data=output_buffer.getvalue(), file_name=f"{uploaded.name.replace('.pdf', '')}_redacted.pdf")

    st.markdown("### 🔎 Redacted Fields Summary")
    st.dataframe(pd.DataFrame(pii_table))

# Manual highlight
elif page_mode == "🖍️ Manual Highlights":
    st.title("🖍️ Manual Highlight Interface")
    if "widgets_df" not in st.session_state or st.session_state["widgets_df"].empty:
        st.warning("No data. Run Auto Redact first.")
    else:
        widgets_df = st.session_state["widgets_df"]
        choice = st.selectbox("Choose a field to review:", widgets_df["Display Name"].unique())
        row = widgets_df[widgets_df["Display Name"] == choice].iloc[0]

        original_text = row["Field Value"]
        doc_cache_key = (row["Page"] - 1, row["Field Name"])
        if doc_cache_key in st.session_state["doc_cache"]:
            field_doc = st.session_state["doc_cache"][doc_cache_key]
        else:
            field_doc = nlp(original_text)
            st.session_state["doc_cache"][doc_cache_key] = field_doc
        
        if "correction_cache" not in st.session_state:
            st.session_state["correction_cache"] = {}



        highlighted = original_text
        for ent in sorted(field_doc.ents, key=lambda x: -len(x.text)):
            if ent.label_ in PII_COLORS:
                span = f"<span style='background-color:{PII_COLORS[ent.label_]}; padding:2px'>{ent.text} ({ent.label_})</span>"
                highlighted = highlighted.replace(ent.text, span)

        st.markdown("**🖍 Highlighted Original:**", unsafe_allow_html=True)
        st.markdown(f"<div style='border:1px solid #ccc; padding:10px'>{highlighted}</div>", unsafe_allow_html=True)

        st.markdown("#### ✅ Select Entities to Redact")
        redact_flags = {
            (ent.start_char, ent.end_char, ent.text, ent.label_): st.checkbox(f"{ent.text} ({ent.label_})", value=True)
            for ent in field_doc.ents if ent.label_ in PII_COLORS
        }

        redacted_preview = original_text
        for start, end, text, label in sorted(redact_flags.keys(), key=lambda x: -x[0]):
            if redact_flags[(start, end, text, label)]:
                tag = f"(({label}))"
                pad = max(0, len(text) - len(tag))
                redacted_preview = redacted_preview[:start] + " " * pad + tag + redacted_preview[end:]

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔍 Before")
            st.text_area("Original", original_text, height=200)
        with col2:
            st.subheader("🔒 After")
            st.text_area("Redacted Preview", redacted_preview, height=200)

        pii_data = [{
            "Page": row["Page"],
            "Field Name": row["Field Name"],
            "input": ent.text,
            "output": f"(({ent.label_}))",
            "Display Name": row["Display Name"]
        } for ent in field_doc.ents if ent.label_ in PII_COLORS]

        if pii_data:
            st.markdown("### 📋 Field Redaction Summary")
            st.dataframe(pd.DataFrame(pii_data))

            for page_num, page in enumerate(doc):
                if page_num == row["Page"] - 1:
                    for widget in page.widgets():
                        if widget.field_name == row["Field Name"]:
                            widget.field_value = redacted_preview
                            widget.update()

            buf = io.BytesIO()
            doc.save(buf)

            st.download_button("⬇️ Download Updated PDF", data=buf.getvalue(), file_name=f"{uploaded.name.replace('.pdf', '')}_manual_redacted.pdf")




#%%%  Fallback Engine - Deterministic Pattern Recognition
elif page_mode == " 📦 Fallback Engine":
        
        
        st.title("📦 Deterministic Pattern Recognition")
        DETERMINISTIC_PATTERNS = {
            "DATE (dpr)": r"\b(?:\d{1,2}(?:st|nd|rd|th)?[\s/\-]?)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,\-]*\d{2,4}\b",
            "SSN (dpr)": r"\b\d{3}-\d{2}-\d{4}\b",
            "MRN (dpr)": r"\b(?:MRN[:\s]*)?\d{6,10}\b",
            "PHONE (dpr)": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
            "EMAIL (dpr)": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            "DRUG (dpr)": r"\b(?:acetaminophen|ibuprofen|amoxicillin|lisinopril|atorvastatin)\b",
            "DEVICE (dpr)": r"\b(?:model|serial)[:\s]*[A-Z0-9\-]{3,}"
        }

        if "widgets_df" not in st.session_state:
            st.warning("No redacted PDF found. Run Auto Redact first.")
        else:
            widgets_df = st.session_state["widgets_df"]
            choice = st.selectbox("Choose a field to review:", widgets_df["Display Name"].unique())
            row = widgets_df[widgets_df["Display Name"] == choice].iloc[0]

            text = row["Field Value"]
            matches = []

            for label, pattern in DETERMINISTIC_PATTERNS.items():
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    matches.append((match.start(), match.end(), match.group(), label))

            # Highlighted version
            highlighted = text
            for start, end, val, label in sorted(matches, key=lambda x: -x[0]):
                span = f"<span style='background-color:khaki; padding:2px'>{val} ({label})</span>"
                highlighted = highlighted[:start] + span + highlighted[end:]

            st.markdown("**🖍 Highlighted Original with Deterministic Labels:**", unsafe_allow_html=True)
            st.markdown(f"<div style='border:1px solid #ccc; padding:10px'>{highlighted}</div>", unsafe_allow_html=True)

            st.markdown("#### ✅ Select Entities to Redact (Deterministic)")
            redact_flags = {
                (start, end, val, label): st.checkbox(f"{val} ({label})", value=True)
                for start, end, val, label in matches
            }

            # Redacted preview
            redacted_preview = text
            for start, end, val, label in sorted(redact_flags.keys(), key=lambda x: -x[0]):
                if redact_flags[(start, end, val, label)]:
                    tag = f"(({label}))"
                    pad = max(0, len(val) - len(tag))
                    redacted_preview = redacted_preview[:start] + " " * pad + tag + redacted_preview[end:]

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔍 Before")
                st.text_area("Original", text, height=200)
            with col2:
                st.subheader("🔒 After")
                st.text_area("Redacted Preview", redacted_preview, height=200)

            pii_data = [{
                "Page": row["Page"],
                "Field Name": row["Field Name"],
                "input": val,
                "output": f"(({label}))",
                "Display Name": row["Display Name"]
            } for start, end, val, label in matches if redact_flags.get((start, end, val, label), False)]

            if pii_data:
                st.markdown("### 📋 Field Redaction Summary (Deterministic)")
                st.dataframe(pd.DataFrame(pii_data))

                for page_num, page in enumerate(doc):
                    if page_num == row["Page"] - 1:
                        for widget in page.widgets():
                            if widget.field_name == row["Field Name"]:
                                widget.field_value = redacted_preview
                                widget.update()

                buf = io.BytesIO()
                doc.save(buf)
                st.download_button("⬇️ Download Fallback Redacted PDF", data=buf.getvalue(), file_name=f"{uploaded.name.replace('.pdf', '')}_fallback_redacted.pdf")

