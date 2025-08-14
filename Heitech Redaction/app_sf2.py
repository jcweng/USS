import streamlit as st
import spacy
from spacy.pipeline import EntityRuler
from streamlit_pdf_viewer import pdf_viewer
import fitz  # PyMuPDF
import pandas as pd
import io

# Load spaCy model with custom address patterns
nlp = spacy.load("en_core_web_trf")
ruler = nlp.add_pipe("entity_ruler", before="ner")
# %%%
patterns = [
    {
        "label": "ADDRESS",
        "pattern": [
            {"IS_DIGIT": True},
            {"LOWER": {"REGEX": r"[a-z]+"}},
            {"LOWER": {"REGEX": r"[a-z]+"}},
            {"LOWER": {"REGEX": r"[a-z]+"}},
            {"IS_ALPHA": True, "LENGTH": 2}
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
    "CARDINAL": "lightgray",
    "ADDRESS": "lightblue"
}
# %%%
# Upload PDF
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file is None:
    st.stop()

# Open PDF and show full text for reference
doc_pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
# full_text = "\n\n".join([page.get_text() for page in doc_pdf])


st.subheader("📄 Full PDF Text (Reference Only)")
# st.text(full_text)

if uploaded_file is not None:
    # Read the uploaded file as bytes
    binary_data = uploaded_file.getvalue()

    # Display the PDF using streamlit_pdf_viewer   
    pdf_viewer(
        binary_data,
        width=700,
        height=1000,
        zoom_level=1.2,                    # 120% zoom
        viewer_align="center",             # Center alignment
        show_page_separator=True           # Show separators between pages
        )


# Extract form fields (fillable values only)
form_fields = []
for page_num, page in enumerate(doc_pdf):
    widgets = page.widgets()
    if widgets:
        for widget in widgets:
            if widget.field_type == fitz.PDF_WIDGET_TYPE_TEXT and widget.field_value:
                form_fields.append({
                    "page": page_num,
                    "value": widget.field_value,
                    "rect": widget.rect,
                    "widget": widget
                })

# Combine fillable values for NLP
field_text = " ".join(f["value"] for f in form_fields)

st.subheader("📝 Original Fillable Field Text")
st.text(field_text)

# Run spaCy on fillable content only
doc = nlp(field_text)

# Highlighted PII
st.subheader("🔎 Highlighted PII in Fillable Fields")
highlighted = ""
cursor = 0
for ent in doc.ents:
    highlighted += field_text[cursor:ent.start_char]
    color = PII_COLORS.get(ent.label_, "orange")
    highlighted += f'<span style="background-color:{color}; padding:2px;">{ent.text}</span>'
    cursor = ent.end_char
highlighted += field_text[cursor:]
st.markdown(highlighted, unsafe_allow_html=True)

# Build dataframe of detected PII
entities = [{"Text": ent.text, "Label": ent.label_} for ent in doc.ents]
df = pd.DataFrame(entities).drop_duplicates()

st.subheader("📋 Detected PII Entities")
st.dataframe(df)

# PII toggle
if "selected_redact" not in st.session_state:
    st.session_state.selected_redact = set((ent.text, ent.label_) for ent in doc.ents)

st.subheader("👁️ Toggle PII to Unredact")
for ent in df.itertuples():
    key = f"toggle-{ent.Text}-{ent.Label}"
    default = (ent.Text, ent.Label) in st.session_state.selected_redact
    if st.checkbox(f"{ent.Label}: {ent.Text}", value=default, key=key):
        st.session_state.selected_redact.add((ent.Text, ent.Label))
    else:
        st.session_state.selected_redact.discard((ent.Text, ent.Label))

# Redaction and save
if st.button("🔏 Generate Redacted PDF"):
    redacted_doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")

    for field in form_fields:
        redact_this = False
        for text, label in st.session_state.selected_redact:
            if text in field["value"]:
                redact_this = True
                break

        if redact_this:
            page = redacted_doc[field["page"]]
            page.add_redact_annot(field["rect"], text=label, fill=(0, 0, 0), text_color=(1, 1, 1), align=1)
            page.apply_redactions()

    output = io.BytesIO()
    redacted_doc.save(output)
    redacted_doc.close()

    st.download_button("⬇️ Download Redacted PDF", data=output.getvalue(), file_name="redacted.pdf")
