# -*- coding: utf-8 -*-
"""
Created on Mon Jul  7 15:48:48 2025

@author: peace
"""

import streamlit as st
import spacy

# Load spaCy model
nlp = spacy.load('en_core_web_trf')

# Define PII types and their display colors
PII_COLORS = {
    "PERSON": "lightblue",
    "GPE": "lightgreen",
    "DATE": "lightpink",
    "ORG": "lightyellow",
    "LOC": "lavender",
    "CARDINAL": "lightgray"
}

# File uploader
uploaded_file = st.file_uploader("Upload a file", type=["txt"], accept_multiple_files=False)

if uploaded_file is not None:
    text = uploaded_file.read().decode("utf-8")
    st.subheader("📄 Original Text")
    st.text(text)

    # Run spaCy NER
    doc = nlp(text)

    # Build HTML with color highlights
    html_output = ""
    last_end = 0

    for ent in doc.ents:
        # Append text before entity
        html_output += text[last_end:ent.start_char]

        color = PII_COLORS.get(ent.label_, None)
        if color:
            html_output += f'<span style="background-color:{color}; padding:2px;">{ent.text}</span>'
        else:
            html_output += ent.text

        last_end = ent.end_char

    # Append remaining text
    html_output += text[last_end:]

    # Display highlighted result
    st.subheader("🔎 Highlighted PII")
    st.markdown(html_output, unsafe_allow_html=True)
