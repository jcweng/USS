# PDF_PII_redactor_SL_v4-3.py

import os
import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import spacy
import io
import re
import threading
import base64
from datetime import datetime
from streamlit_pdf_viewer import pdf_viewer
from spacy.pipeline import EntityRuler
from spacy import displacy

# Env & API setup
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# Setup SymSpell
from symspellpy.symspellpy import SymSpell, Verbosity

import importlib.resources

dictionary_path = importlib.resources.files("symspellpy") / "frequency_dictionary_en_82_765.txt"
sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1):
    st.error("⚠️ SymSpell dictionary failed to load.")
    st.stop()

# Page config with custom theme - Force light mode
st.set_page_config(
    layout="wide",
    page_title="CLARA",
    page_icon="clara_logo.png",
    initial_sidebar_state="collapsed"
)

# Force Streamlit to use light theme
os.environ['STREAMLIT_THEME_BASE'] = 'light'

# Apply custom Streamlit theme styling
st.markdown("""
<style>
:root {
    --primary-color: #0272B7;
}

/* Custom styling for selected tag buttons - light green */
.stButton > button[data-baseweb="button"][kind="primary"] {
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    color: white !important;
}

.stButton > button[data-baseweb="button"][kind="primary"]:hover {
    background-color: #218838 !important;
    border-color: #1e7e34 !important;
}

/* Force light mode - override dark mode detection */
.stApp {
    background-color: white !important;
    color: black !important;
}

.stSidebar {
    background-color: #f0f2f6 !important;
}

/* Make header bar match sidebar color */
.stHeader {
    background-color: #f0f2f6 !important;
}

header[data-testid="stHeader"] {
    background-color: #f0f2f6 !important;
}

.stMarkdown, .stText {
    color: black !important;
}

/* Force all text elements to black in light mode */
label, .stSelectbox label, .stTextInput label, .stTextArea label,
.stCheckbox label, .stRadio label, .stSlider label,
p, span, div, .element-container, .stSelectbox div,
.stAlert, .stInfo, .stSuccess, .stWarning, .stError {
    color: black !important;
}

/* Ensure form labels are black */
.stSelectbox > label, .stTextInput > label, .stTextArea > label,
.stCheckbox > label, .stRadio > label, .stSlider > label,
.stFileUploader > label {
    color: black !important;
}

/* Override Streamlit's primary color elements */
.stButton > button {
    background-color: #0272B7 !important;
    border-color: #0272B7 !important;
    color: white !important;
}

/* Ensure download buttons match the theme */
.stDownloadButton > button, [data-testid="stDownloadButton"] button {
    background-color: #0272B7 !important;
    border-color: #0272B7 !important;
    color: white !important;
    font-weight: 500 !important;
}

.stDownloadButton > button:hover, [data-testid="stDownloadButton"] button:hover {
    background-color: #025a9e !important;
    border-color: #025a9e !important;
}

/* Center download buttons */
.stDownloadButton {
    text-align: center !important;
    display: flex !important;
    justify-content: center !important;
}

.stSelectbox > div > div > div {
    border-color: #0272B7 !important;
    background-color: white !important;
    color: black !important;
}

.stCheckbox > label > div[data-testid="stCheckbox"] > div {
    background-color: #0272B7 !important;
}

.stRadio > label > div[data-testid="stRadio"] > div {
    background-color: #0272B7 !important;
}

.stSlider > div > div > div > div {
    background-color: #0272B7 !important;
}

.stProgress > div > div > div > div {
    background-color: #0272B7 !important;
}

/* Style progress bars - center and improve appearance */
.stProgress {
    max-width: 600px !important;
    margin: 1rem auto !important;
    text-align: center !important;
}

.stProgress > div {
    background-color: #f0f2f6 !important;
    border-radius: 10px !important;
    height: 20px !important;
}

.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #0272B7, #0298e6) !important;
    border-radius: 10px !important;
    height: 20px !important;
}

/* File uploader - keep outer container default, style inner drag zone only */
.stFileUploader {
    background-color: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* Target the inner drag and drop zone specifically */
.stFileUploader [data-testid="stFileUploaderDropzone"],
.stFileUploader > div > div > div {
    background-color: #f0f2f6 !important;
    border: 1px solid #ddd !important;
    border-radius: 8px !important;
}

.stFileUploader [data-testid="stFileUploaderDropzone"]:hover,
.stFileUploader > div > div > div:hover {
    border-color: #0272B7 !important;
    background-color: #f0f2f6 !important;
}

/* Browse files button styling - complementary grey, slightly darker than drag zone */
.stFileUploader button,
.stFileUploader [data-testid="stFileUploaderDropzone"] button {
    background-color: #e8eaed !important;
    color: #4a5568 !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}

.stFileUploader button:hover,
.stFileUploader [data-testid="stFileUploaderDropzone"] button:hover {
    background-color: #dde1e6 !important;
    border-color: #0272B7 !important;
}

/* Center main page content with much wider layout */
.main .block-container {
    text-align: center !important;
    max-width: 95% !important;
    width: 95% !important;
    margin: 0 auto !important;
    padding-top: 2rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* Override Streamlit's default container constraints */
.stApp > .main > .block-container {
    max-width: 95% !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* Make sure content containers use full available width */
.element-container {
    max-width: 100% !important;
}

/* Center the main title with full width */
h1 {
    text-align: center !important;
    margin-bottom: 1rem !important;
    width: 100% !important;
    max-width: none !important;
}

/* Center file uploader elements with wider width */
.stFileUploader {
    text-align: left !important;
    margin: 2rem auto !important;
    max-width: 50% !important;
    width: 50% !important;
}

.stFileUploader > label {
    text-align: left !important;
    font-size: 1.2rem !important;
    font-weight: 500 !important;
    margin-bottom: 1rem !important;
    display: block !important;
    width: 100% !important;
}

/* Center drag and drop zone content */
.stFileUploader [data-testid="stFileUploaderDropzone"],
.stFileUploader > div > div > div {
    text-align: center !important;
    padding: 3rem 3rem !important;
}

/* Center any informational text */
.stInfo, .stSuccess, .stMarkdown {
    text-align: center !important;
    max-width: 1200px !important;
    margin: 1rem auto !important;
}

/* Header logo styling */
.header-logo {
    position: fixed;
    top: 1rem;
    left: 1rem;
    z-index: 999;
    width: 80px;
    height: 80px;
}

/* Force light backgrounds for input elements */
.stTextInput > div > div > input {
    background-color: white !important;
    color: black !important;
    border: 1px solid #ddd !important;
}

.stTextArea > div > div > textarea {
    background-color: white !important;
    color: black !important;
    border: 1px solid #ddd !important;
}

/* Override any dark mode media queries */
@media (prefers-color-scheme: dark) {
    .stApp {
        background-color: white !important;
        color: black !important;
    }
    
    .stSidebar {
        background-color: #f0f2f6 !important;
    }
    
    .stMarkdown, .stText {
        color: black !important;
    }
}

/* Simple dataframe styling for light mode */
[data-testid="stDataFrame"] > div {
    background-color: #f0f2f6 !important;
    border-radius: 8px !important;
    border: 1px solid #ddd !important;
}

/* Enhanced PDF viewer styling with scrollbars and pan functionality */
iframe[title="streamlit_pdf_viewer.pdf_viewer"] {
    border: 1px solid #ddd !important;
    border-radius: 8px !important;
    overflow: auto !important;
}

/* PDF viewer container styling */
div[data-testid="stIframe"] {
    overflow: auto !important;
    border: 1px solid #ddd !important;
    border-radius: 8px !important;
    background-color: white !important;
}

/* Enable scrolling and dragging in PDF viewers */
.stIframe iframe {
    overflow: auto !important;
    scrollbar-width: thin !important;
}

/* Custom scrollbar styling for PDF viewers */
.stIframe iframe::-webkit-scrollbar {
    width: 12px !important;
    height: 12px !important;
}

.stIframe iframe::-webkit-scrollbar-track {
    background: #f1f1f1 !important;
    border-radius: 6px !important;
}

.stIframe iframe::-webkit-scrollbar-thumb {
    background: #0272B7 !important;
    border-radius: 6px !important;
}

.stIframe iframe::-webkit-scrollbar-thumb:hover {
    background: #025a9e !important;
}

/* Enable pan functionality by ensuring overflow is visible */
.stIframe {
    position: relative !important;
    overflow: visible !important;
}
</style>
""", unsafe_allow_html=True)

if "doc_cache" not in st.session_state:
    st.session_state["doc_cache"] = {}

if "correction_cache" not in st.session_state:
    st.session_state["correction_cache"] = {}

# Full width title using st.title to avoid markdown constraints
st.markdown("<h1 style='text-align: center;'>FDA 3500A MedWatch Form Redaction System</h1>", unsafe_allow_html=True)

# Sidebar navigation with automatic redirection support and query parameters
st.sidebar.header("Select PII Types to Redact")
pii_types = st.sidebar.multiselect(
    "Choose PII types to redact:",
    options=["ADDRESS", "DATE", "SSN", "PERSON", "ORG"],
    default=["ADDRESS", "DATE", "SSN"]  # Default selections
)
if "goto" in st.query_params and st.query_params["goto"] == "edit":
    default_index = 1  # Edit (now index 1)
    st.query_params.clear()  # Clear the parameter
elif "redirect_to_edit" in st.session_state and st.session_state["redirect_to_edit"]:
    default_index = 1  # Edit (now index 1)
    st.session_state["redirect_to_edit"] = False
else:
    default_index = 0  # Upload PDF

# Store the current page mode to prevent navigation issues
if "current_page_mode" not in st.session_state:
    st.session_state["current_page_mode"] = default_index
else:
    # Update from query parameter if needed
    if "goto" in st.query_params and st.query_params["goto"] == "edit":
        st.session_state["current_page_mode"] = 1

# Single radio button call with unique key
options = ["Upload PDF", "Verify", "Edit"]
page_mode = st.sidebar.radio(
    "Navigation",
    options,
    index=st.session_state["current_page_mode"],
    key="main_navigation"
)

# Update current page mode when user changes it manually
options = ["Upload PDF", "Verify", "Edit"]
for i, option in enumerate(options):
    if option == page_mode and i != st.session_state["current_page_mode"]:
        st.session_state["current_page_mode"] = i
        break

PATTERNS = [
    {"label": "ADDRESS", "pattern": [{"TEXT": {"REGEX": r"^\d{3,6}$"}}, {"IS_ALPHA": True, "OP": "+"}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True, "OP": "+"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_PUNCT": True, "OP": "?"}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "ADDRESS", "pattern": [{"IS_DIGIT": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_ALPHA": True, "OP": "?"}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True}, {"IS_PUNCT": True, "OP": "?"}, {"IS_ALPHA": True, "LENGTH": 2}, {"IS_DIGIT": True, "LENGTH": 5}]},
    {"label": "DATE", "pattern": [{"IS_DIGIT": True}, {"LOWER": {"REGEX": "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"}}, {"IS_DIGIT": True}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}-\d{2}-\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"^\d{3}$"}}, {"TEXT": "-"}, {"TEXT": {"REGEX": r"^\d{2}$"}}, {"TEXT": "-"}, {"TEXT": {"REGEX": r"^\d{4}$"}}]},
    {"label": "SSN", "pattern": [{"TEXT": {"REGEX": r"(?i)^(ssn|ss|social|security)[:]?$"}}, {"TEXT": {"REGEX": r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"}}]}
]

# Cached NLP loader with fallback models
@st.cache_resource
def load_nlp():
    models_to_try = ["en_core_web_trf", "en_core_web_lg", "en_core_web_md", "en_core_web_sm"]
    
    for model_name in models_to_try:
        try:
            nlp = spacy.load(model_name)
            # st.info(f"✅ Loaded spaCy model: {model_name}")  # Removed to clean up UI
            ruler = nlp.add_pipe("entity_ruler", before="ner")
            ruler.add_patterns(PATTERNS)
            return nlp
        except OSError:
            st.warning(f"⚠️ Model {model_name} not found, trying next...")
            continue
    
    # If no models found, show error and stop
    st.error("❌ No spaCy English models found. Please install one using: python -m spacy download en_core_web_sm")
    st.stop()

nlp = load_nlp()

# AFTER:
PII_COLORS = {
    "ADDRESS": "#009E73", 
    "DATE": "#CC79A7", 
    "SSN": "#D55E00",
    "PERSON": "#E69F00",
    "ORG": "#0272B7", 
    "GPE": "#F0E442",
    "PHONE": "#56B4E9"
}


# Correction engine
@st.cache_data(show_spinner=False)
def apply_text_corrections(text, spell_level, grammar_level, fluency_level):
    if spell_level == grammar_level == fluency_level == "disable":
        return text

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
    # Full width filename display
    st.markdown(f"<div style='text-align: center;'><strong>✅ Using uploaded file:</strong> {uploaded.name}</div>", unsafe_allow_html=True)

# Upload tab UI
if page_mode == "Upload PDF":
    # Get binary data for use throughout this section
    binary_data = uploaded.getvalue()
    
    # Set hardcoded defaults for correction levels
    st.session_state["spell_level"] = "1"
    st.session_state["grammar_level"] = "1"
    st.session_state["fluency_level"] = "disable"
    st.session_state["doc_cache"] = {}
    st.session_state["correction_cache"] = {}
    
    # Initialize processing tracking
    if "processing_complete" not in st.session_state:
        st.session_state["processing_complete"] = False
    
    if not st.session_state["processing_complete"]:
        import time
        
        # Phase 1: PDF Upload (0-20%)
        progress_text = "PDF uploading..."
        my_bar = st.progress(0, text=progress_text)
        for percent_complete in range(20):
            time.sleep(0.02)
            my_bar.progress(percent_complete + 1, text=progress_text)
        
        # Phase 2: Loading NLP Models (20-40%)
        progress_text = "Upload complete..."
        for percent_complete in range(20, 40):
            time.sleep(0.03)
            my_bar.progress(percent_complete + 1, text=progress_text)
        
        # Phase 3: Document Analysis (40-70%)
        progress_text = "Initializing PII detection..."
        for percent_complete in range(40, 70):
            time.sleep(0.025)
            my_bar.progress(percent_complete + 1, text=progress_text)
        
        # Phase 4: Applying Redactions (70-95%)
        progress_text = "Analyzing and redacting..."
        for percent_complete in range(70, 95):
            time.sleep(0.03)
            my_bar.progress(percent_complete + 1, text=progress_text)
        
        # Phase 5: Finalizing (95-100%)
        progress_text = "Finalizing redaction process..."
        for percent_complete in range(95, 100):
            time.sleep(0.05)
            my_bar.progress(percent_complete + 1, text=progress_text)
        
        # Complete
        my_bar.progress(100, text="✅ Initial redactions complete!")
        time.sleep(1.5)
        my_bar.empty()
        
        st.session_state["processing_complete"] = True
        st.success("✅ Processing complete! PDF previewer loading...")
        time.sleep(1)
        
        # Process the PDF now instead of redirecting
        if "widgets_df" not in st.session_state:
            # Setup processing variables
            doc = fitz.open(stream=binary_data, filetype="pdf")
            widgets_df = []
            pii_table = []
            output_buffer = io.BytesIO()
            
            text_correction_levels = (
                st.session_state.get("spell_level", "disable"),
                st.session_state.get("grammar_level", "disable"),
                st.session_state.get("fluency_level", "disable"))

            def correct_field_text(val):
                norm = re.sub(r"\s+", " ", val.replace("\n", " ").strip())
                key = (norm, text_correction_levels)
                if key in st.session_state["correction_cache"]:
                    return st.session_state["correction_cache"][key]
                corrected = apply_text_corrections(norm, *text_correction_levels)
                st.session_state["correction_cache"][key] = corrected
                return corrected
            
            # Open the document once and process it
            doc = fitz.open(stream=binary_data, filetype="pdf")
            for page_num in range(doc.page_count):
                page = doc[page_num]
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

                        # Only add to pii_table if there's actual meaningful text content
                        norm_corrected = re.sub(r"\s+", " ", corrected.replace("\n", " ").strip())
                        # More aggressive filtering - check if normalized text has actual letters/numbers
                        if norm_corrected and re.search(r'[a-zA-Z0-9]', norm_corrected):
                            pii_table.append({
                                "Page": page_num + 1,
                                "Section": display_name,
                                "Original": corrected,
                                "Redaction": redacted
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
            st.session_state["pii_table"] = pii_table
            st.session_state["output_buffer"] = output_buffer
        
        st.rerun()
    
    # Show results if processing is complete
    if st.session_state.get("processing_complete", False) and "widgets_df" in st.session_state:
        st.markdown("---")
        
        # PDF Viewers with wider width
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Original PDF")
            pdf_viewer(binary_data, width=900, height=800, key="original_upload")
        with col2:
            st.subheader("Redacted Preview")
            pdf_viewer(st.session_state["output_buffer"].getvalue(), width=900, height=800, key="redacted_upload")

        st.markdown("### Initial Redaction Summary")
        
        # Configure dataframe with proper column settings for text wrapping
        pii_table = st.session_state.get("pii_table", [])
        if pii_table:
            df = pd.DataFrame(pii_table)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Page": st.column_config.NumberColumn("Page", width="small"),
                    "Section": st.column_config.TextColumn("Section", width="small"),
                    "Original": st.column_config.TextColumn("Original", width="large"),
                    "Redaction": st.column_config.TextColumn("Redaction", width="large")
                })
        else:
            st.info("No PII data to display")

        # Center the edit and clear buttons
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
        with col3:
            if st.button("Edit and Review", type="secondary", use_container_width=True):
                # Redirect to Edit page by updating session state
                st.session_state["current_page_mode"] = 1  # Edit index
                st.rerun()
        with col5:
            if st.button("❌ Clear Uploaded PDF", key="clear_pdf_upload", type="secondary", use_container_width=True):
                st.session_state.pop("uploaded_file", None)
                st.session_state["processing_complete"] = False
                st.session_state.pop("widgets_df", None)
                st.session_state.pop("pii_table", None)
                st.session_state.pop("output_buffer", None)
                # Clear editor tags and buffers when clearing PDF
                if "editor_tags" in st.session_state:
                    st.session_state["editor_tags"] = []
                if "final_pdf_buffer" in st.session_state:
                    st.session_state.pop("final_pdf_buffer", None)
                if "final_pdf_summary" in st.session_state:
                    st.session_state.pop("final_pdf_summary", None)
                st.rerun()

# After upload
binary_data = uploaded.getvalue()
# Store original PDF data before any processing
original_pdf_data = binary_data
doc = fitz.open(stream=binary_data, filetype="pdf")

text_correction_levels = (
    st.session_state.get("spell_level", "disable"),
    st.session_state.get("grammar_level", "disable"),
    st.session_state.get("fluency_level", "disable"))

st.session_state["full_text"] = "".join([p.get_text() for p in doc])

@st.cache_data
def correct_field_text(val):
    norm = re.sub(r"\s+", " ", val.replace("\n", " ").strip())
    key = (norm, text_correction_levels)
    if key in st.session_state["correction_cache"]:
        return st.session_state["correction_cache"][key]
    corrected = apply_text_corrections(norm, *text_correction_levels)
    st.session_state["correction_cache"][key] = corrected
    return corrected

# Manual highlight --> "Verify"
if page_mode == "Verify":
    st.markdown("<h1 style='text-align: center;'>Verify Initial Redactions</h1>", unsafe_allow_html=True)
    
    # Initialize verify-specific session state
    if "verify_selections" not in st.session_state:
        st.session_state["verify_selections"] = {}
    
    if "widgets_df" not in st.session_state or st.session_state["widgets_df"].empty:
        st.warning("No data. Upload a file first.")

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
        
        # Generate redact flags with persistent state
        redact_flags = {}
        field_key = f"{row['Display Name']}_entities"
        
        for ent in field_doc.ents:
            if ent.label_ in PII_COLORS:
                ent_key = (ent.start_char, ent.end_char, ent.text, ent.label_)
                # Use stored state if available, otherwise default to True
                if field_key in st.session_state["verify_selections"]:
                    redact_flags[ent_key] = st.session_state["verify_selections"][field_key].get(ent_key, True)
                else:
                    redact_flags[ent_key] = True
        
        # Only highlight entities that are selected for redaction
        for ent in sorted(field_doc.ents, key=lambda x: -len(x.text)):
            if ent.label_ in PII_COLORS:
                ent_key = (ent.start_char, ent.end_char, ent.text, ent.label_)
                if redact_flags.get(ent_key, True):  # Only highlight if selected
                    span = f"<span style='background-color:{PII_COLORS[ent.label_]}; padding:2px'>{ent.text} ({ent.label_})</span>"
                    highlighted = highlighted.replace(ent.text, span)


        st.markdown("**Highlighted Original:**", unsafe_allow_html=True)
        st.markdown(f"<div style='border:1px solid #ccc; padding:10px' id='highlighted-text'>{highlighted}</div>", unsafe_allow_html=True)

        st.markdown("#### Select Entities to Redact")
        
        # Create checkboxes and update session state
        current_selections = {}
        for ent in field_doc.ents:
            if ent.label_ in PII_COLORS:
                ent_key = (ent.start_char, ent.end_char, ent.text, ent.label_)
                current_value = redact_flags.get(ent_key, True)
                
                checkbox_value = st.checkbox(
                    f"{ent.text} ({ent.label_})", 
                    value=current_value,
                    key=f"redact_{field_key}_{ent.start_char}_{ent.end_char}"
                )
                current_selections[ent_key] = checkbox_value
                redact_flags[ent_key] = checkbox_value
        
        # Store current selections in session state
        st.session_state["verify_selections"][field_key] = current_selections

        redacted_preview = original_text
        # Sort by position (descending) to avoid index shifting issues
        for start, end, text, label in sorted(redact_flags.keys(), key=lambda x: -x[0]):
            if redact_flags[(start, end, text, label)]:
                tag = f"(({label}))"
                pad = max(0, len(text) - len(tag))
                redacted_preview = redacted_preview[:start] + " " * pad + tag + redacted_preview[end:]

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Original Text")
            st.text_area("Unredacted Version", original_text, height=200)
        with col2:
            st.subheader("Initial Redaction")
            st.text_area("Preview of Redacted Version", redacted_preview, height=200)

        pii_data = [{
            "Page": row["Page"],
            "Section": row["Display Name"],
            "Section Name": row["Field Name"],
            "Original": ent.text,
            "Redaction": f"(({ent.label_}))"
        } for ent in field_doc.ents if ent.label_ in PII_COLORS]

# Filter PII data to only include selected items
        pii_data = [{
            "Page": row["Page"],
            "Section": row["Display Name"],
            "Section Name": row["Field Name"],
            "Original": text,
            "Redaction": f"(({label}))"
        } for (start, end, text, label) in redact_flags.keys() 
          if redact_flags[(start, end, text, label)]]

        if pii_data:
            st.markdown("### Redaction Summary")
            st.dataframe(pd.DataFrame(pii_data))

            # Update the PDF with current redaction state
            for page_num, page in enumerate(doc):
                if page_num == row["Page"] - 1:
                    for widget in page.widgets():
                        if widget.field_name == row["Field Name"]:
                            widget.field_value = redacted_preview
                            widget.update()

            buf = io.BytesIO()
            doc.save(buf)

            st.download_button("⬇️ Download Updated PDF", data=buf.getvalue(), file_name=f"{uploaded.name.replace('.pdf', '')}_manual_redacted.pdf")

        # Add separator and Continue Redacting button at the bottom
        st.markdown("---")

        # Center the Continue Redacting button
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            if st.button("Continue Redacting", 
                        type="primary", 
                        use_container_width=True,
                        key="continue_redacting_btn"):
                # Navigate to Edit page by updating session state
                st.session_state["current_page_mode"] = 2  # Edit is index 2
                st.rerun()


# Edit - Click-to-tag interface
if page_mode == "Edit":
    # Add custom CSS for green selected buttons in editor only
    st.markdown("""
    <style>
    /* Override button colors specifically for the editor section */
    .stButton > button {
        background-color: #6c757d !important;
        border-color: #6c757d !important;
        color: white !important;
    }
    
    .stButton > button:hover {
        background-color: #5a6268 !important;
        border-color: #545b62 !important;
    }
    
    /* Green styling for primary/selected buttons using the working selectors */
    .stButton > button[data-testid*="primary"],
    .stButton > button[kind="primary"],
    button[data-testid*="primary"] {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
        color: white !important;
    }
    
    .stButton > button[data-testid*="primary"]:hover,
    .stButton > button[kind="primary"]:hover,
    button[data-testid*="primary"]:hover {
        background-color: #218838 !important;
        border-color: #1e7e34 !important;
    }
    
    /* Blue styling specifically for Tag Word buttons */
    .stButton > button[key*="tag_btn"] {
        background-color: #0272B7 !important;
        border-color: #0272B7 !important;
        color: white !important;
    }
    
    .stButton > button[key*="tag_btn"]:hover {
        background-color: #025a9e !important;
        border-color: #025a9e !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("### Verify and Edit")
    
    # Initialize editor state
    if "editor_tags" not in st.session_state:
        st.session_state["editor_tags"] = []
    if "selected_tag_type" not in st.session_state:
        st.session_state["selected_tag_type"] = None
    
    # Tag selection buttons - always visible
    st.info("Choose the redaction tag you want to apply to the text.")
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        button_text = "✅ B4 - Trade Secrets" if st.session_state["selected_tag_type"] == "B4" else "B4 - Trade Secrets"
        if st.button(button_text,
                    type="primary" if st.session_state["selected_tag_type"] == "B4" else "secondary",
                    use_container_width=True,
                    key="b4_button"):
            st.session_state["selected_tag_type"] = "B4"
    
    with col2:
        button_text = "✅ B6 - Patient Info" if st.session_state["selected_tag_type"] == "B6" else "B6 - Patient Info"
        if st.button(button_text,
                    type="primary" if st.session_state["selected_tag_type"] == "B6" else "secondary",
                    use_container_width=True,
                    key="b6_button"):
            st.session_state["selected_tag_type"] = "B6"
    
    with col3:
        button_text = "✅ Other" if st.session_state["selected_tag_type"] == "Other" else "Other"
        if st.button(button_text,
                    type="primary" if st.session_state["selected_tag_type"] == "Other" else "secondary",
                    use_container_width=True,
                    key="other_button"):
            st.session_state["selected_tag_type"] = "Other"
    
    with col4:
        if st.button("Clear Selection",
                    type="secondary",
                    key="clear_selection_top",
                    use_container_width=True,
                    disabled=st.session_state["selected_tag_type"] is None):
            st.session_state["selected_tag_type"] = None
    
    if "widgets_df" not in st.session_state or st.session_state["widgets_df"].empty:
        st.markdown("---")
        st.warning("No data available. Please upload and process a PDF first to load fields for editing.")
        st.info("Once you upload a PDF, it will be processed and you'll be able to tag specific text within the PDF fields.")
    else:
        # Initialize editor state
        if "editor_tags" not in st.session_state:
            st.session_state["editor_tags"] = []
        if "selected_tag_type" not in st.session_state:
            st.session_state["selected_tag_type"] = None
        
        # Ensure we have redacted PDF data for preview
        if "output_buffer" not in st.session_state or not hasattr(st.session_state, "output_buffer"):
            # Create output buffer from current document state
            temp_output_buffer = io.BytesIO()
            temp_doc = fitz.open(stream=original_pdf_data, filetype="pdf")
            
            # Apply the same redactions as in Auto Redact
            widgets_df = st.session_state["widgets_df"]
            for idx, row in widgets_df.iterrows():
                page_num = row['Page'] - 1
                field_name = row['Field Name']
                
                # Get the redacted field content from widgets_df processing
                for page_num_doc, page in enumerate(temp_doc):
                    if page_num_doc == page_num:
                        for widget in page.widgets() or []:
                            if widget.field_name == field_name:
                                # Apply NLP redactions (same logic as Auto Redact)
                                corrected = correct_field_text(widget.field_value or "")
                                doc_cache_key = (page_num, field_name)
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
                                        continue
                                    redacted = redacted.replace(
                                        ent.text,
                                        f"[{ent.label_}]{' ' * max(0, len(ent.text) - len(ent.label_) - 2)}"
                                    )
                                
                                widget.field_value = redacted
                                widget.update()
                                break
            
            temp_doc.save(temp_output_buffer)
            temp_doc.close()
            st.session_state["output_buffer"] = temp_output_buffer
        
        output_buffer = st.session_state["output_buffer"]
        
        # Text-based tagging interface
        
        if st.session_state["selected_tag_type"]:
            widgets_df = st.session_state["widgets_df"]
            
            # Show all fields at once instead of dropdown selection
            st.markdown("**Redacted Sections of the Uploaded PDF:**")
            st.markdown("*Click on any word to tag and redact it from the PDF.*")
            
            # Process each field that has content
            field_count = 0
            for idx, row in widgets_df.iterrows():
                if row['Field Value'].strip():
                    field_count += 1
                    
                    # Field label - left aligned with no spacing
                    st.markdown(f"<h4 style='text-align: left; margin-bottom: 2px; margin-top: 10px;' onclick=\"highlightText('{row['Display Name']}')\">{row['Display Name']} (Page {row['Page']})</h4>", unsafe_allow_html=True)
                    
                    # Generate redacted version using NLP (same logic as Auto Redact)
                    original_text = row['Field Value']
                    corrected = correct_field_text(original_text)
                    doc_cache_key = (row['Page'] - 1, row['Field Name'])
                    if doc_cache_key in st.session_state["doc_cache"]:
                        doc_ent = st.session_state["doc_cache"][doc_cache_key]
                    else:
                        doc_ent = nlp(corrected)
                        st.session_state["doc_cache"][doc_cache_key] = doc_ent
                    
                    redacted_text = corrected
                    for ent in doc_ent.ents:
                        if ent.label_ in {"CARDINAL", "QUANTITY", "PERCENT"}:
                            continue
                        if ent.label_ in {"FAC", "GPE"} and any(e.label_ == "ADDRESS" for e in doc_ent.ents):
                            continue
                        if ent.label_ == "PERSON" and any(char.isdigit() for char in ent.text):
                            continue
                        if ent.label_ == "DATE" and not re.search(r"(19|20)\d{2}", ent.text):
                            continue
                        redacted_text = redacted_text.replace(
                            ent.text,
                            f"[{ent.label_}]{' ' * max(0, len(ent.text) - len(ent.label_) - 2)}"
                        )
                    
                    
                    # Parse text to get individual words
                    parts = re.split(r'(\[[^\]]+\])', redacted_text)
                    all_words = []
                    
                    for part in parts:
                        if re.match(r'^\[[^\]]+\]$', part):
                            continue  # Skip already redacted parts
                        else:
                            words = part.split()
                            for word in words:
                                if word.strip():
                                    clean_word = word.strip('.,!?;:()[]{}"\'-')
                                    if clean_word and clean_word not in all_words:
                                        all_words.append(clean_word)
                    
                    # Create visual representation
                    display_html = ""
                    for part in parts:
                        if re.match(r'^\[[^\]]+\]$', part):
                            display_html += f'<span style="background-color: #f5f5f5; color: #666; padding: 2px 4px; border-radius: 3px; font-weight: bold; font-family: monospace; margin: 0 2px;">{part}</span>'
                        else:
                            words = part.split()
                            for word in words:
                                if word.strip():
                                    clean_word = word.strip('.,!?;:()[]{}"\'-')
                                    is_tagged = any(tag["text"] == clean_word and tag["field_idx"] == idx
                                                   for tag in st.session_state["editor_tags"])
                                    if is_tagged:
                                        display_html += f'<span style="background-color: #28a745; color: white; padding: 2px 4px; border-radius: 3px; margin: 1px; font-weight: bold;">{word} ✓</span> '
                                    else:
                                        display_html += f'<span>{word}</span> '
                                else:
                                    display_html += " "
                    
                    # Display text in a clean container
                    st.markdown(f"""
                    <div style="
                        border: 1px solid #dee2e6;
                        border-radius: 8px;
                        padding: 20px;
                        background-color: white;
                        line-height: 1.8;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 15px;
                        max-height: 300px;
                        overflow-y: auto;
                        margin: 10px 0;
                    ">
                        {display_html}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Word selection interface - centered with dropdown and button side by side
                    if all_words:
                        col1, col2, col3 = st.columns([1.5, 2, 1.3])
                        with col2:
                            # Filter out already tagged words for the dropdown
                            untagged_words = [word for word in all_words
                                            if not any(tag["text"] == word and tag["field_idx"] == idx
                                                     for tag in st.session_state["editor_tags"])]
                            
                            if untagged_words:
                                # Create a proper inline layout using columns
                                dropdown_col, button_col = st.columns([3, 1])
                                with dropdown_col:
                                    selected_word = st.selectbox(
                                        "Select a word to tag:",
                                        options=[""] + untagged_words,
                                        key=f"word_select_{idx}",
                                        help="Choose a word from the text above to tag"
                                    )
                                with button_col:
                                    # Use empty space to align button with selectbox
                                    st.write("")  # Empty line to create proper spacing
                                    if st.button("Tag Word",
                                                key=f"tag_btn_{idx}",
                                                disabled=not selected_word or not st.session_state["selected_tag_type"],
                                                type="primary",
                                                use_container_width=False):
                                        if selected_word and st.session_state["selected_tag_type"]:
                                            new_tag = {
                                                "text": selected_word,
                                                "type": st.session_state["selected_tag_type"],
                                                "field": row['Display Name'],
                                                "page": row['Page'],
                                                "field_idx": idx
                                            }
                                            st.session_state["editor_tags"].append(new_tag)
                                            st.success(f"Tagged '{selected_word}' as {st.session_state['selected_tag_type']}")
                                            st.session_state["editor_tags"].append({"text": selected_word, "type": st.session_state["selected_tag_type"]})
                                            st.session_state["editor_tags"].append({"text": selected_word, "type": st.session_state["selected_tag_type"]})
                                            st.rerun()
                            else:
                                st.info("All words have been tagged")
                    
                    # Show current tags for this field - centered with light grey background
                    field_tags = [tag for tag in st.session_state["editor_tags"] if tag["field_idx"] == idx]
                    if field_tags:
                        col1, col2, col3 = st.columns([1.2, 1.6, 1.2])
                        with col2:
                            # Use expander with "Tagged words" as header
                            with st.expander("Tagged Words", expanded=True):
                                # Apply custom CSS to style the expander
                                st.markdown("""
                                <style>
                                .streamlit-expanderHeader {
                                    display: none !important;
                                }
                                .streamlit-expanderContent {
                                    background-color: #f8f9fa !important;
                                    border: 1px solid #e9ecef !important;
                                    border-radius: 8px !important;
                                    padding: 15px 15px 15px 15px !important; /* top, right, bottom, left */
                                }
                                .tag-text {
                                    text-align: left !important;
                                    display: block;
                                }
                                /* RIGHT-ALIGN the wrapper and allow it to shrink */
                                div[data-testid="stExpander"] div[data-testid="stButton"],
                                div[data-testid="stExpander"] div[data-testid^="baseButton-"] {
                                    display: flex !important;            /* align contents horizontally */
                                    justify-content: flex-end !important;
                                    width: auto !important;              /* don't force 100% width wrapper */
                                }

                                /* Let the actual <button> size to its content and shrink on narrow screens */
                                div[data-testid="stExpander"] div[data-testid="stButton"] > button,
                                div[data-testid="stExpander"] div[data-testid^="baseButton-"] > button {
                                    width: auto !important;              /* override Streamlit's default */
                                    min-width: 0 !important;
                                    max-width: 100% !important;
                                    white-space: nowrap;
                                    padding: 0.45rem 0.65rem !important; /* base size */
                                    font-size: 0.90rem !important;
                                }


                                /* Medium screens: shave size */
                                @media (max-width: 900px) {
                                    div[data-testid="stExpander"] div[data-testid="stButton"] > button,
                                    div[data-testid="stExpander"] div[data-testid^="baseButton-"] > button {
                                        padding: 0.35rem 0.55rem !important;
                                        font-size: 0.85rem !important;
                                    }
                                }

                                /* Small screens: smallest comfortable tap target */
                                @media (max-width: 640px) {
                                    div[data-testid="stExpander"] div[data-testid="stButton"] > button,
                                    div[data-testid="stExpander"] div[data-testid^="baseButton-"] > button {
                                        padding: 0.30rem 0.50rem !important;
                                        font-size: 0.80rem !important;
                                    }
                                }
                                </style>
                                """, unsafe_allow_html=True)
                                
                                # Display tags within the styled container
                                for i, tag in enumerate(field_tags):
                                    tag_col1, tag_col2 = st.columns([3.5, .75])
                                    with tag_col1:
                                        st.markdown(f"<span class='tag-text'><b>{tag['type']}</b>: `{tag['text']}`</span>", unsafe_allow_html=True)
                                    with tag_col2:
                                        if st.button("Remove", key=f"remove_tag_{idx}_{i}"):
                                            st.session_state["editor_tags"] = [
                                                t for t in st.session_state["editor_tags"]
                                                if not (t["text"] == tag["text"] and t["field_idx"] == idx)
                                            ]
                                            st.success(f"Removed tag from '{tag['text']}'")
                                            st.rerun()
                    
                    # Add some spacing between fields
                    st.markdown("---")
            if field_count == 0:
                st.warning("No fields with content available for tagging")
        else:
            st.warning("Please select a tag type first")
        
        # Statistics
        b4_count = len([t for t in st.session_state["editor_tags"] if t["type"] == "B4"])
        b6_count = len([t for t in st.session_state["editor_tags"] if t["type"] == "B6"])
        other_count = len([t for t in st.session_state["editor_tags"] if t["type"] == "Other"])
        
        # Statistics display - centered with subheader
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader("Redactions Added")
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            with metric_col1:
                st.metric("Total Tags", len(st.session_state["editor_tags"]))
            with metric_col2:
                st.metric("B4", b4_count)
            with metric_col3:
                st.metric("B6", b6_count)
            with metric_col4:
                st.metric("Other", other_count)
        
        st.markdown("---")

        if "download_complete" not in st.session_state:
            st.session_state["download_complete"] = False
        
        def _mark_download_complete():
            st.session_state["download_complete"] = True

        # Generate / Preview final PDF and download at the bottom - centered
        if st.session_state["editor_tags"]:
            col1, col2, col3 = st.columns([2, 1, 2])
            with col2:
                preview_clicked = st.button("Preview Final Redacted PDF", type="secondary", use_container_width=True, key="btn_preview_final")

            if preview_clicked:
                try:
                    # ---- REQUIRE a FULL-DOC NLP-REDACTED BUFFER (no fallback to original) ----
                    base_buf = st.session_state.get("output_buffer")

                    if base_buf is None:
                        raise RuntimeError(
                            "Missing full-document NLP-redacted buffer "
                            "(expected st.session_state['output_buffer'])."
                        )


                    base_bytes = base_buf.getvalue() if hasattr(base_buf, "getvalue") else base_buf
                    _check = fitz.open(stream=base_bytes, filetype="pdf")
                    required_pages = int(widgets_df["Page"].max())
                    if _check.page_count < required_pages:
                        pc = _check.page_count
                        _check.close()
                        raise RuntimeError(
                            f"NLP-redacted buffer has {pc} page(s) but tags reference up to page {required_pages}. "
                            "Upstream redaction must produce a FULL-DOCUMENT buffer. "
                            "Store it in st.session_state['output_buffer_full']."
                        )
                    _check.close()

                    # Open full doc (already NLP-redacted) to layer editor tags
                    final_doc = fitz.open(stream=base_bytes, filetype="pdf")

                    # Map type -> label text used in brackets (user tag label wins if present)
                    TYPE_LABELS = {
                        "B4": "trade secret",
                        "B6": "patient info",
                    }

                    # Group tags by field index
                    by_field = {}
                    for tag in st.session_state["editor_tags"]:
                        by_field.setdefault(tag["field_idx"], []).append(tag)

                    updated_pii_table = []
                    for field_idx, tags in by_field.items():
                        row = widgets_df.iloc[field_idx]
                        page_num   = int(row["Page"]) - 1
                        field_name = row["Field Name"]

                        # Read the current (already NLP-redacted) value from the PDF as the base
                        page = final_doc[page_num]
                        field_widget = None
                        for w in (page.widgets() or []):
                            if w.field_name == field_name:
                                field_widget = w
                                break

                        base_text = field_widget.field_value if (field_widget and field_widget.field_value is not None) else row["Field Value"]


                        # Safety: page must exist in the full-doc base
                        if not (0 <= page_num < final_doc.page_count):
                            raise RuntimeError(
                                f"Tag for page {row['Page']} but base has {final_doc.page_count} pages. "
                                "Your base must be full-document."
                            )

                        # Apply user tags (longest first to avoid partial overlaps)
                        if ent.label_ in pii_types:  # Check if the entity label is in the selected PII types
                            redacted = base_text
                        for t in sorted(tags, key=lambda x: len(x["text"]), reverse=True):
                            ttype = (t.get("type") or "").upper()
                            lbl   = t.get("label") or TYPE_LABELS.get(ttype, "redacted")
                            replacement = f"[{ttype or 'TAG'} - {lbl}]"
                            redacted = redacted.replace(t["text"], replacement)

                        # Write back into the form field on that page
                        page = final_doc[page_num]
                        wrote = False
                        for widget in (page.widgets() or []):
                            if widget.field_name == field_name:
                                widget.field_value = redacted
                                widget.update()
                                wrote = True
                                break
                        if not wrote:
                            # Hard fail: your data says the field is on this page but we couldn't find it
                            raise RuntimeError(f"Form field '{field_name}' not found on page {row['Page']}.")
                    
                        updated_pii_table.append({
                            "Page": row["Page"],
                            "Section": row["Display Name"],
                            "Original": base_text,
                            "Redaction": redacted,
                        })

                    # Buffer the result
                    final_buffer = io.BytesIO()
                    final_doc.save(final_buffer)
                    final_doc.close()

                    if preview_clicked:
                        # Store and render the WHOLE final doc
                        st.session_state["final_preview_buffer"] = final_buffer
                        st.session_state["final_pdf_buffer"] = final_buffer          # NEW: also store for download
                        st.session_state["final_pdf_summary"] = updated_pii_table     # NEW: keep summary in sync
                        st.session_state["show_final_preview"] = True 

                        st.markdown("### Preview: Final Redacted PDF")
                        from streamlit_pdf_viewer import pdf_viewer
                        pdf_viewer(
                            st.session_state["final_preview_buffer"].getvalue(),
                            width=900, height=900, key="final_preview"
                        )

                            # NEW: download button directly under the preview
                        d1, d2, d3 = st.columns([2, 1.5, 2])
                        with d2:
                            downloaded_after_preview = st.download_button(
                                "⬇️ Download Final Redacted PDF",
                                data=st.session_state["final_pdf_buffer"].getvalue(),
                                file_name=f"{uploaded.name.replace('.pdf', '')}_redacted.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key="download_after_preview",  # ensure a distinct key
                                on_click=_mark_download_complete,
                            )
                            if downloaded_after_preview:
                                st.session_state["download_complete"] = True 

                    else:
                        # Persist for summary + download
                        st.session_state["final_pdf_buffer"]  = final_buffer
                        st.session_state["final_pdf_summary"] = updated_pii_table
                        st.success("Final PDF generated!")

                except Exception as e:
                    st.error(f"Error: {e}")

        
        # Show final summary and download if PDF has been generated
        if "final_pdf_buffer" in st.session_state and "final_pdf_summary" in st.session_state and not st.session_state.get("show_final_preview", False):

            # Download button at the bottom
            col1, col2, col3 = st.columns([2, 1.5, 2])
            with col2:
                st.download_button(
                    "⬇️ Download Final Redacted PDF",
                    data=st.session_state["final_pdf_buffer"].getvalue(),
                    file_name=f"{uploaded.name.replace('.pdf', '')}_final_redacted.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_bottom",
                    on_click=_mark_download_complete,
                )
                if downloaded_bottom:
                    st.session_state["download_complete"] = True

        # Show a single "Start Over" button bottom-right only AFTER a download click
        if st.session_state.get("download_complete", False):
            spacer, right = st.columns([5, 1])  # bottom-right placement
            with right:
                if st.button("Start the next Redaction", type="secondary", use_container_width=True, key="btn_start_over"):
                    # Clear all state (uploads, tags, buffers, caches) and restart
                    st.session_state.clear()
                    st.session_state["download_complete"] = False
                    st.rerun()