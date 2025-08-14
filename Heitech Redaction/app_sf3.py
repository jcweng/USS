import streamlit as st
import spacy
from spacy.pipeline import EntityRuler
import fitz  # PyMuPDF
import pandas as pd
import io
from streamlit_pdf_viewer import pdf_viewer

st.set_page_config(layout="wide")

# Load spaCy with EntityRuler
nlp = spacy.load("en_core_web_trf")
ruler = nlp.add_pipe("entity_ruler", before="ner")
patterns = [{
    "label": "ADDRESS",
    "pattern": [
        {"IS_DIGIT": True},
        {"LOWER": {"REGEX": r"[a-z]+"}},
        {"LOWER": {"REGEX": r"[a-z]+"}},
        {"LOWER": {"REGEX": r"[a-z]+"}},
        {"IS_ALPHA": True, "LENGTH": 2}
    ]
}]
ruler.add_patterns(patterns)

PII_COLORS = {
    "PERSON": "pink",
    "GPE": "lightgreen",
    "DATE": "lightpink",
    "ORG": "lightyellow",
    "LOC": "lavender",
    "CARDINAL": "lightgray",
    "ADDRESS": "lightblue"
}

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file is not None:
    binary_data = uploaded_file.getvalue()
    doc_pdf = fitz.open(stream=binary_data, filetype="pdf")

    # Extract fillable fields
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
    if "field_redact_map" not in st.session_state:
        st.session_state.field_redact_map = {}

    for field in form_fields:
        field_doc = nlp(field["value"])
        for ent in field_doc.ents:
            pii_labels.add(ent.label_)
            key = (field["page"], field["field_name"], ent.text, ent.label_)
            if key not in st.session_state.field_redact_map:
                st.session_state.field_redact_map[key] = True
            pii_rows.append({
                "Page": field["page"] + 1,
                "Field Name": field["field_name"],
                "Text": ent.text,
                "Label": ent.label_
            })

    pii_df = pd.DataFrame(pii_rows).drop_duplicates()

    # Layout: PDF and Highlighted Preview
    col1, col2 = st.columns([2, 2])
    with col1:
        st.subheader("📄 Full PDF Text (Reference Only)")
        pdf_viewer(
            binary_data,
            width=1000,
            height=1000,
            zoom_level=1,
            viewer_align="center",
            show_page_separator=True
        )

    with col2:
        st.subheader("🖍️ PDF with Color Coded PII")
        pii_preview_doc = fitz.open(stream=binary_data, filetype="pdf")

        # Highlight only actual PII spans inside fillable fields
        for field in form_fields:
            field_doc = nlp(field["value"])
            page = pii_preview_doc[field["page"]]
            words = page.get_text("words")
            for ent in field_doc.ents:
                for w in words:
                    if w[4] == ent.text:
                        rect = fitz.Rect(w[0], w[1], w[2], w[3])
                        color = PII_COLORS.get(ent.label_, "red")
                        page.draw_rect(rect, color=fitz.utils.getColor(color), fill=fitz.utils.getColor(color), overlay=True)

        preview_buffer = io.BytesIO()
        pii_preview_doc.save(preview_buffer, incremental=False, garbage=4)
        pii_preview_doc.close()

        pdf_viewer(
            preview_buffer.getvalue(),
            width=1000,
            height=1000,
            zoom_level=1,
            viewer_align="center",
            show_page_separator=True
        )

    st.subheader("🔍 PII Redline Preview in Fillable Fields")
    
    # Redact by label type control
    redact_labels = {}
    cols = st.columns(len(pii_labels))
    for i, label in enumerate(sorted(pii_labels)):
        redact_labels[label] = cols[i].checkbox(f"Redact {label}", value=True)
    
    # Condensed view per page: each page gets a vertical list in a column
    pages_with_data = sorted(pii_df["Page"].unique())
    page_columns = st.columns(len(pages_with_data))
    for col_idx, page_num in enumerate(pages_with_data):
        with page_columns[col_idx]:
            st.markdown(f"### 📄 Page {page_num}")
            page_fields = [f for f in form_fields if f["page"] + 1 == page_num]
    
            for field in page_fields:
                field_doc = nlp(field["value"])
                ents = list(field_doc.ents)
                if not ents:
                    continue
    
                st.markdown(f"**Field:** `{field['field_name']}`")
                text_display = field["value"]
                for ent in ents:
                    highlight = f"▶ [{ent.label_}] {ent.text}"
                    text_display = text_display.replace(ent.text, highlight)
                st.text(text_display)
    
                for ent in ents:
                    key = (field["page"], field["field_name"], ent.text, ent.label_)
                    if redact_labels.get(ent.label_, True):
                        st.session_state.field_redact_map[key] = True
                    checked = st.checkbox(
                        f"Redact [{ent.label_}] '{ent.text}'",
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
            width=600,
            height=600,
            zoom_level=1,
            viewer_align="center",
            show_page_separator=True
        )

        st.download_button("⬇️ Download Redacted PDF", data=output_pdf.getvalue(), file_name="redacted.pdf")
else:
    st.info("Please upload a PDF to begin.")
