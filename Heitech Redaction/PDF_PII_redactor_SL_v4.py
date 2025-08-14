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

os.chdir(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(".env")
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Page config and title
st.set_page_config(layout="wide")
st.title("📑 PDF PII Redactor with Manual Highlight")

# Sidebar control to clear uploaded file
if st.sidebar.button("❌ Clear Uploaded PDF"):
    st.session_state.pop("uploaded_file", None)
    st.experimental_rerun()

# Sidebar navigation
page_mode = st.sidebar.radio("📂 Navigation", ["📥 Upload PDF", "🔒 Auto Redact", "🖍️ Manual Highlights"])

# Load spaCy NLP model with patterns
nlp = spacy.load("en_core_web_trf")
ruler = nlp.add_pipe("entity_ruler", before="ner")
patterns = [
    {"label": "ADDRESS", "pattern": [{"TEXT": {"regex": r"^\d{3,6}$"}}, {"IS_ALPHA": True, "OP": "+"}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True, "OP": "+"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_PUNCT": True, "OP": "?"}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "ADDRESS", "pattern": [{"IS_DIGIT": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "DATE", "pattern": [{"IS_DIGIT": True}, {"LOWER": {"regex": "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"}}, {"IS_DIGIT": True}]},
    {"label": "SSN", "pattern": [{"TEXT": {"regex": r"^\d{3}-\d{2}-\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"regex": r"^\d{3}$"}}, {"TEXT": "-"}, {"TEXT": {"regex": r"^\d{2}$"}}, {"TEXT": "-"}, {"TEXT": {"regex": r"^\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"regex": r"^(ssn|ss|social|security)[:]?$", "flags": "i"}}, {"TEXT": {"regex": r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"}}]}
]
ruler.add_patterns(patterns)

PII_COLORS = {"ADDRESS": "lightblue", "DATE": "lightpink", "SSN": "orange"}
@st.cache_data(show_spinner=False)
def apply_text_corrections(text, spell_level, grammar_level, fluency_level):
    if spell_level == grammar_level == fluency_level == "disable":
        return text

    # If any OpenAI model selected
    if "3" in (spell_level, grammar_level, fluency_level):
        instruction = []
        if spell_level == "3":
            instruction.append("fix spelling")
        if grammar_level == "3":
            instruction.append("correct grammar")
        if fluency_level == "3":
            instruction.append("rewrite for clarity and fluency")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant. Please {' and '.join(instruction)}."},
                {"role": "user", "content": text}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()

    # Local-only pipeline
    corrected_text = text

    if spell_level == "1":
        from spellchecker import SpellChecker
        spell = SpellChecker()
        corrected_text = " ".join([spell.correction(w) or w for w in corrected_text.split()])

    if grammar_level == "1":
        from grammar_checker import grammar_check_with_languagetool
        corrected_text = grammar_check_with_languagetool(corrected_text)

    if fluency_level == "1":
        # Could be expanded with simple heuristics or templates
        corrected_text = corrected_text  # Placeholder

    return corrected_text


def grammar_check_with_languagetool(text):
    import language_tool_python
    tool = language_tool_python.LanguageTool("en-US")
    matches = tool.check(text)
    return language_tool_python.utils.correct(text, matches)


# File uploader with persistence
if "uploaded_file" not in st.session_state:
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded:
        st.session_state.uploaded_file = uploaded
else:
    uploaded = st.session_state.uploaded_file
    st.markdown(f"**✅ Using uploaded file:** {uploaded.name}")

if page_mode == "📥 Upload PDF":
    st.subheader("📥 Upload PDF")
    st.write("Use this page to upload your PDF before redacting.")

    col1, col2 = st.columns(2)
    with col1:
        spell_level = st.selectbox("Spelling Correction", options=["disable", "1", "2", "3"])
    with col2:
        grammar_level = st.selectbox("Grammar Correction", options=["disable", "1", "2", "3"])

    fluency_level = st.selectbox("Language Fluency Rewrite", options=["disable", "1"])

    st.write(f"🔤 Spelling: {spell_level}, 🧠 Grammar: {grammar_level}, ✍️ Fluency: {fluency_level}")

    sample_text = st.text_area("Paste some sample text to preview correction:", "The quick brown fox jumpps ovver the lazi dog.", height=150)
    def correct_text_preview(sample_text, spell_level):
        return apply_text_corrections(sample_text, spell_level)

    if st.button("✅ Run Preview on Sample Text"):
        preview_output = correct_text_preview(sample_text, spell_level)
        st.markdown("**🔧 Corrected Output:**")
        st.text_area("Corrected Text", preview_output, height=150)

    if st.button("✅ Apply Selection to Main Document"):
        st.session_state["spell_level"] = spell_level
        st.session_state["grammar_level"] = grammar_level
        st.session_state["fluency_level"] = fluency_level
        st.success("✅ Configuration applied. Go to 🔒 Auto Redact or 🖍️ Manual Highlights to continue.")



    st.stop()

if "uploaded_file" in st.session_state:
    uploaded_file = st.session_state.uploaded_file
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

        st.download_button("⬇️ Download Redacted PDF", data=output_buffer.getvalue(), file_name=f"{uploaded_file.name.replace('.pdf', '')}_redacted.pdf")

        st.markdown("### 🔎 Redacted Fields Summary")
        st.dataframe(pd.DataFrame(pii_table))

#%%% Manual Highlight Section
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
    
            st.markdown("**🖍 Highlighted Original with Labels:**", unsafe_allow_html=True)
            st.markdown(f"<div style='border:1px solid #ccc; padding:10px'>{highlighted}</div>", unsafe_allow_html=True)
    
            # CHECKBOX SECTION: User-selectable redaction toggles
            st.markdown("#### ✅ Select Entities to Redact")
            redact_flags = {}
            for ent in field_doc.ents:
                if ent.label_ in PII_COLORS:
                    label_text = f"{ent.text} ({ent.label_})"
                    default_checked = True
                    redact_flags[(ent.start_char, ent.end_char, ent.text, ent.label_)] = st.checkbox(label_text, value=default_checked)
    
            # Generate redacted preview with user-selected checkboxes
            redacted_preview = original_text
            for start, end, text, label in sorted(redact_flags.keys(), key=lambda x: -x[0]):
                if redact_flags[(start, end, text, label)]:
                    tag = f"(({label}))"
                    padding = max(0, len(text) - len(tag))
                    replacement = " " * padding + tag
                    redacted_preview = redacted_preview[:start] + replacement + redacted_preview[end:]
    
            # DISPLAY SIDE-BY-SIDE TEXT AREAS
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔍 Before")
                st.text_area("Original Text", original_text, height=200)
    
            with col2:
                st.subheader("🔒 After")
                st.text_area("Redacted Preview", redacted_preview, height=200)
    
            # Table summary for this field
            pii_data = []
            for ent in field_doc.ents:
                if ent.label_ in PII_COLORS:
                    pii_data.append({
                        "Page": selected_row["Page"],
                        "Field Name": selected_row["Field Name"],
                        "input": ent.text,
                        "output": f"(({ent.label_}))",
                        "Display Name": selected_row["Display Name"]
                    })
    
            if pii_data:
                st.markdown("### 📋 Field Redaction Summary")
                st.dataframe(pd.DataFrame(pii_data))

                # Generate downloadable redacted PDF using in-memory doc
                for page_num, page in enumerate(doc):
                    if page_num == selected_row["Page"] - 1:
                        for widget in page.widgets():
                            if widget.field_name == selected_row["Field Name"]:
                                widget.field_value = redacted_preview
                                widget.update()

                output_buffer_manual = io.BytesIO()
                doc.save(output_buffer_manual)

                st.download_button(

                    label="⬇️ Download Updated PDF with Manual Redaction",
                    data=output_buffer_manual.getvalue(),
                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_redacted.pdf",
                    mime="application/pdf"
                )