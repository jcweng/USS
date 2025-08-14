import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import spacy
import io
import re
from streamlit_pdf_viewer import pdf_viewer
from spacy.pipeline import EntityRuler
from spacy import displacy

# Page config and title
st.set_page_config(layout="wide")
st.title("📑 PDF PII Redactor with Manual Highlight")

# Sidebar navigation
page_mode = st.sidebar.radio("📂 Navigation", ["🔒 Auto Redact", "🖍️ Manual Highlights"])

# Load spaCy NLP model with patterns
nlp = spacy.load("en_core_web_trf")
ruler = nlp.add_pipe("entity_ruler", before="ner")
patterns = [
    {"label": "ADDRESS", "pattern": [{"TEXT": {"REGEX": r"^\d{3,6}$"}}, {"IS_ALPHA": True, "OP": "+"}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True, "OP": "+"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_PUNCT": True, "OP": "?"}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "ADDRESS", "pattern": [{"IS_DIGIT": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "DATE", "pattern": [{"IS_DIGIT": True}, {"LOWER": {"REGEX": "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"}}, {"IS_DIGIT": True}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}-\d{2}-\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}$"}}, {"TEXT": "-"}, {"TEXT": {"REGEX": r"^\d{2}$"}}, {"TEXT": "-"}, {"TEXT": {"REGEX": r"^\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^(ssn|ss|social|security)[:]?$", "flags": "i"}}, {"TEXT": {"REGEX": r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"}}]}
]
ruler.add_patterns(patterns)

PII_COLORS = {"ADDRESS": "lightblue", "DATE": "lightpink", "SSN": "orange"}

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    binary_data = uploaded_file.getvalue()
    doc = fitz.open(stream=binary_data, filetype="pdf")

    st.session_state["full_text"] = "".join([p.get_text() for p in doc])

    # Track widget data
    widgets_df = []
    pii_table = []
    output_buffer = io.BytesIO()

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

                # REDACTION TARGET FILTER
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

                    norm_val = re.sub(r"\s+", " ", val.replace("\n", " ").strip())
                    doc_ent = nlp(norm_val)
                    redacted_val = norm_val

                    for ent in doc_ent.ents:
                        if ent.label_ in {"CARDINAL", "QUANTITY", "PERCENT"}:
                            continue
                        if ent.label_ in {"FAC", "GPE"} and any(e.label_ == "ADDRESS" for e in doc_ent.ents):
                            continue
                        if ent.label_ == "PERSON" and any(char.isdigit() for char in ent.text):
                            continue
                        if ent.label_ == "DATE" and not re.search(r"\b(19|20)\d{2}\b", ent.text):
                            continue

                        redacted_val = redacted_val.replace(
                            ent.text,
                            f"[{ent.label_}]{' ' * max(0, len(ent.text) - len(ent.label_) - 2)}"
                        )

                    pii_table.append({
                        "Page": page_num + 1,
                        "Field Name": fname,
                        "input": norm_val,
                        "output": redacted_val,
                        "Display Name": display_name
                    })

                    widget.field_value = redacted_val
                    widget.update()

                    widgets_df.append({
                        "Page": page_num + 1,
                        "Field Name": fname,
                        "Field Value": norm_val,
                        "Display Name": display_name
                    })

        doc.save(output_buffer)
        doc.close()
        st.session_state["widgets_df"] = pd.DataFrame(widgets_df)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📄 Full PDF Text (Reference Only)")
            pdf_viewer(binary_data, width=900, height=900, key="original")

        with col2:
            st.subheader("📄 Redacted PDF Preview")
            pdf_viewer(output_buffer.getvalue(), width=900, height=900, key="redacted")

        st.download_button("⬇️ Download Redacted PDF", data=output_buffer.getvalue(), file_name="redacted_output.pdf")

        st.markdown("### 🔎 Redacted Fields Summary")
        st.dataframe(pd.DataFrame(pii_table))

    #%%%
    elif page_mode == "🖍️ Manual Highlights":
        st.title("🖍️ Manual Highlight Interface")
        st.markdown("Review and preview how redaction would appear for targeted form fields.")

        if "widgets_df" not in st.session_state or st.session_state["widgets_df"].empty:
            st.warning("No form fields available. Please upload a PDF with fillable fields.")
        else:
            widgets_df = st.session_state["widgets_df"]
            dropdown_choices = widgets_df["Display Name"].unique().tolist()
            selected_display = st.selectbox("Choose a field to review:", dropdown_choices)

            selected_row = widgets_df[widgets_df["Display Name"] == selected_display].iloc[0]
            original_text = selected_row["Field Value"]
            field_doc = nlp(original_text)

            # Highlighted inline entity markup
            highlighted = original_text
            for ent in sorted(field_doc.ents, key=lambda x: -len(x.text)):
                if ent.label_ in PII_COLORS:
                    label_str = f"{ent.text} ({ent.label_})"
                    span = f"<span style='background-color:{PII_COLORS[ent.label_]}; padding:2px'>{label_str}</span>"
                    highlighted = highlighted.replace(ent.text, span)

            preview_text = original_text
            for ent in field_doc.ents:
                if ent.label_ in PII_COLORS:
                    preview_text = preview_text.replace(
                        ent.text,
                        f"[{ent.label_}]{' ' * max(0, len(ent.text) - len(ent.label_) - 2)}"
                    )

            st.markdown("**🖍 Highlighted Original with Labels:**", unsafe_allow_html=True)
            st.markdown(f"<div style='border:1px solid #ccc; padding:10px'>{highlighted}</div>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔍 Before")
                st.text_area("Original Text", original_text, height=200)

            with col2:
                st.subheader("🔒 After")
                st.text_area("Redacted Preview", preview_text, height=200)
