# -*- coding: utf-8 -*-
"""
Created on Thu Jul  3 16:18:50 2025

@author: peace
"""

import streamlit as st

st.title("File Processor")

uploaded_file = st.file_uploader("Upload a file", type=["txt"], accept_multiple_files=False)

if uploaded_file is not None:
    st.write("File uploaded:", uploaded_file.name)
    
    if st.button("Run"):
        # Read original file
        input_text = uploaded_file.read().decode("utf-8")
        
        # Modify content
        output_text = input_text + "\nwritten here"
        
        # Convert to bytes for download
        result_bytes = output_text.encode("utf-8")
        
        # Download link
        st.download_button(
            label="Download modified file",
            data=result_bytes,
            file_name="modified_" + uploaded_file.name,
            mime="text/plain"
        )
