import streamlit as st
import spacy
from spacy.pipeline import EntityRuler
import fitz  # PyMuPDF
import pandas as pd
import io
from streamlit_pdf_viewer import pdf_viewer
import re

st.set_page_config(layout="wide")

# Load spaCy with EntityRuler
nlp = spacy.load("en_core_web_trf")
ruler = nlp.add_pipe("entity_ruler", before="ner")
patterns = [{
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
}]
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
    doc_pdf = fitz.open(stream=binary_data, filetype="pdf")

    form_fields = []
    for page_num, page in enumerate(doc_pdf):
        widgets = page.widgets()
        if widgets:
            for widget in widgets:
                if widget.field_type == fitz.PDF_WIDGET_TYPE_TEXT and widget.field_value:
                    form_fields.append({
                        "page": page_num,
                        "field_name": widget.field_name,
                        "value": widget.field_value,
                        "rect": widget.rect,
                        "widget": widget
                    })

    pii_rows = []
    pii_labels = set()
    pii_keys = set()
    if "field_redact_map" not in st.session_state:
        st.session_state.field_redact_map = {}

    for field in form_fields:
        field_doc = nlp(field["value"])
        has_address = any(e.label_ == "ADDRESS" for e in field_doc.ents)
        for ent in field_doc.ents:
            if ent.label_ in {"CARDINAL", "QUANTITY"}:
                continue
            if ent.label_ in {"FAC", "GPE"} and has_address:
                continue
            if ent.label_ == "PERSON" and any(char.isdigit() for char in ent.text):
                continue
            if ent.label_ == "DATE":
                # Skip if it's a single char or doesn't contain a year-like 4-digit number
                if len(ent.text.strip()) == 1 or not re.search(r"\b(19|20)\d{2}\b", ent.text):
                    continue
            key = (field["page"], field["field_name"], ent.text, ent.label_)
            pii_keys.add(key)
            if key not in st.session_state.field_redact_map:
                st.session_state.field_redact_map[key] = True
            pii_labels.add(ent.label_)
            pii_rows.append({
                "Page": field["page"] + 1,
                "Field Name": field["field_name"],
                "Text": ent.text,
                "Label": ent.label_
            })

    pii_df = pd.DataFrame(pii_rows).drop_duplicates()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📄 Full PDF Text (Reference Only)")
        pdf_viewer(
            binary_data,
            width=900,
            height=900,
            zoom_level=1,
            viewer_align="center",
            show_page_separator=True
        )

    with col2:
        st.subheader("🖍️ PDF with Color Coded PII")
        pii_preview_doc = fitz.open(stream=binary_data, filetype="pdf")
        for field in form_fields:
            field_doc = nlp(field["value"])
            has_address = any(e.label_ == "ADDRESS" for e in field_doc.ents)
            page = pii_preview_doc[field["page"]]
            words = page.get_text("words")
            for ent in field_doc.ents:
                key = (field["page"], field["field_name"], ent.text, ent.label_)
                if key not in pii_keys:
                    continue
                ent_words = [w for w in words if w[4] == ent.text]
                if ent_words:
                    x0 = min(w[0] for w in ent_words)
                    y0 = min(w[1] for w in ent_words)
                    x1 = max(w[2] for w in ent_words)
                    y1 = max(w[3] for w in ent_words)
                    rect = fitz.Rect(x0, y0, x1, y1)
                    color = PII_COLORS.get(ent.label_, "red")
                    page.draw_rect(rect, color=fitz.utils.getColor(color), fill=fitz.utils.getColor(color), overlay=True)

        preview_buffer = io.BytesIO()
        pii_preview_doc.save(preview_buffer, incremental=False, garbage=4)
        pii_preview_doc.close()

        pdf_viewer(
            preview_buffer.getvalue(),
            width=900,
            height=900,
            zoom_level=1,
            viewer_align="center",
            show_page_separator=True
        )

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
            page_fields = [f for f in form_fields if f["page"] + 1 == page_num]
            for field in page_fields:
                field_doc = nlp(field["value"])
                ents = [e for e in field_doc.ents if (field["page"], field["field_name"], e.text, e.label_) in pii_keys]
                if not ents:
                    continue
                st.markdown(f"**Field:** `{field['field_name']}`")
                for ent in ents:
                    key = (field["page"], field["field_name"], ent.text, ent.label_)
                    if redact_labels.get(ent.label_, True):
                        st.session_state.field_redact_map[key] = True
                    checked = st.checkbox(
                        f"{ent.text}   *{ent.label_}*",
                        value=st.session_state.field_redact_map[key],
                        key=str(key)
                    )
                    st.session_state.field_redact_map[key] = checked

    st.subheader("📋 Detected PII Entities")
    st.dataframe(pii_df)

    if st.button("🔏 Generate Redacted PDF"):
        redacted_doc = fitz.open(stream=binary_data, filetype="pdf")
        for page_num, page in enumerate(redacted_doc):
            words = page.get_text("words")
            for (f_page, field_name, text, label), should_redact in st.session_state.field_redact_map.items():
                if should_redact and f_page == page_num:
                    for w in words:
                        if w[4] == text:
                            rect = fitz.Rect(w[0], w[1], w[2], w[3])
                            page.add_redact_annot(rect, text=label, fill=(0, 0, 0), text_color=(1, 1, 1), align=1)
                    page.apply_redactions()

        output_pdf = io.BytesIO()
        redacted_doc.save(output_pdf)
        redacted_doc.close()

        st.subheader("📄 Redacted PDF Preview")
        pdf_viewer(
            output_pdf.getvalue(),
            width=900,
            height=900,
            zoom_level=1,
            viewer_align="center",
            show_page_separator=True
        )

        st.download_button("⬇️ Download Redacted PDF", data=output_pdf.getvalue(), file_name="redacted.pdf")
else:
    st.info("Please upload a PDF to begin.")
