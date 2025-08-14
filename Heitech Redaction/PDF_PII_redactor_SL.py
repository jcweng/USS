import streamlit as st
import spacy
from spacy.pipeline import EntityRuler
import fitz  # PyMuPDF
import pandas as pd
import io
from streamlit_pdf_viewer import pdf_viewer
import re

st.set_page_config(layout="wide")

# Load spaCy and custom patterns
nlp = spacy.load("en_core_web_trf")
ruler = nlp.add_pipe("entity_ruler", before="ner")
patterns = [
    {
        "label": "ADDRESS",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{3,6}$"}},
            {"IS_ALPHA": True, "OP": "+"},
            {"IS_ALPHA": True, "OP": "?"},
            {"IS_ALPHA": True, "OP": "+"},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_ALPHA": True, "LENGTH": 2},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_DIGIT": True, "LENGTH": 5}
        ]
    },
    {
        "label": "ADDRESS",
        "pattern": [
            {"IS_DIGIT": True},
            {"IS_ALPHA": True, "OP": "?"},
            {"IS_ALPHA": True},
            {"IS_ALPHA": True, "OP": "?"},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_ALPHA": True},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_ALPHA": True, "LENGTH": 2},
            {"IS_DIGIT": True, "LENGTH": 5}
        ]
    },
    
    {
        "label": "DATE",
        "pattern": [
            {"IS_DIGIT": True},
            {"LOWER": {"REGEX": "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"}},
            {"IS_DIGIT": True}
        ]
    },
    {
        "label": "SSN",
        "pattern": [{"TEXT": {"REGEX": r"^\d{3}-\d{2}-\d{4}$"}}]
    },
    {
        "label": "SSN",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{3}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{2}$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{4}$"}}
        ]
    },
    {
        "label": "SSN",
        "pattern": [
            {"TEXT": {"REGEX": r"^(ssn|ss|social|security)[:]?$", "flags": "i"}},
            {"TEXT": {"REGEX": r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"}}
        ]
    }
]

ruler.add_patterns(patterns)

PII_COLORS = {
    "PERSON": "pink",
    "GPE": "lightgreen",
    "DATE": "lightpink",
    "ORG": "lightyellow",
    "LOC": "lavender",
    "ADDRESS": "lightblue"
}

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file is not None:
    binary_data = uploaded_file.getvalue()
    doc = fitz.open(stream=binary_data, filetype="pdf")

    if "field_redact_map" not in st.session_state:
        st.session_state.field_redact_map = {}

    form_fields = []
    pii_rows = []
    unmatched = []
    redaction_count = 0
    pii_labels = set()
    pii_keys = set()

    for page_num, page in enumerate(doc):
        widgets = page.widgets()
        if not widgets:
            continue

        for widget in widgets:
            if widget.field_type != fitz.PDF_WIDGET_TYPE_TEXT or not widget.field_value:
                continue

            original_value = widget.field_value
            normalized_value = re.sub(r"\s+", " ", original_value.replace("\n", " ").strip())
            redacted_value = normalized_value
            field_doc = nlp(normalized_value)

            has_address = any(e.label_ == "ADDRESS" for e in field_doc.ents)

            for ent in field_doc.ents:
                if ent.label_ in {"CARDINAL", "QUANTITY", "PERCENT"}:
                    continue
                if ent.label_ in {"FAC", "GPE"} and has_address:
                    continue
                if ent.label_ == "PERSON" and any(char.isdigit() for char in ent.text):
                    continue
                if ent.label_ == "DATE":
                    if len(ent.text.strip()) == 1 or not re.search(r"\b(19|20)\d{2}\b", ent.text.lower()):
                        continue

                key = (page_num, widget.field_name, ent.text, ent.label_)
                pii_keys.add(key)
                pii_labels.add(ent.label_)

                replacement = f"[{ent.label_}]{' ' * max(0, len(ent.text) - len(ent.label_) - 2)}"
                if ent.text in redacted_value:
                    redacted_value = redacted_value.replace(ent.text, replacement)
                    redaction_count += 1
                    pii_rows.append({
                        "Page": page_num + 1,
                        "Field Name": widget.field_name,
                        "Text": ent.text,
                        "Label": ent.label_
                    })
                else:
                    unmatched.append((page_num + 1, widget.field_name, ent.text, ent.label_))

            widget.field_value = redacted_value
            widget.update()

    output_buffer = io.BytesIO()
    doc.save(output_buffer)
    doc.close()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📄 Full PDF Text (Reference Only)")
        pdf_viewer(
            binary_data,
            width=900,
            height=900,
            show_page_separator=True
        )

    with col2:
        st.subheader("📄 Redacted PDF Preview")
        pdf_viewer(
            output_buffer.getvalue(),
            width=900,
            height=900,
            show_page_separator=True
        )
        st.download_button("⬇️ Download Redacted PDF", data=output_buffer.getvalue(), file_name="redacted_output.pdf")

    pii_df = pd.DataFrame(pii_rows).drop_duplicates()

    st.subheader("🔍 PII Redline Preview in Fillable Fields")
    redact_labels = {}
    cols = st.columns(len(pii_labels))
    for i, label in enumerate(sorted(pii_labels)):
        redact_labels[label] = cols[i].checkbox(f"Redact {label}", value=True)

    pages_with_data = sorted(pii_df["Page"].unique())
    page_columns = st.columns(len(pages_with_data))
    for col_idx, page_num in enumerate(pages_with_data):
        with page_columns[col_idx]:
            st.markdown(f"### 📄 Page {page_num}")
            page_fields = [r for r in pii_rows if r["Page"] == page_num]
            field_names = set(r["Field Name"] for r in page_fields)
            for fname in sorted(field_names):
                ents = [r for r in page_fields if r["Field Name"] == fname]
                if not ents:
                    continue
                st.markdown(f"**Field:** `{fname}`")
                for ent in ents:
                    key = (page_num - 1, fname, ent["Text"], ent["Label"])
                    if redact_labels.get(ent["Label"], True):
                        st.session_state.field_redact_map[key] = True
                    checked = st.checkbox(
                        f"{ent['Text']}  \t*{ent['Label']}*",
                        value=st.session_state.field_redact_map.get(key, True),
                        key=str(key)
                    )
                    st.session_state.field_redact_map[key] = checked

    st.subheader("📋 Detected PII Entities")
    st.dataframe(pii_df)

    if unmatched:
        st.subheader("⚠️ Unmatched Redaction Targets")
        for entry in unmatched:
            st.write(f"Page {entry[0]} | Field: {entry[1]} | Label: {entry[3]} | Text: {entry[2]}")
else:
    st.info("Please upload a PDF to begin.")
