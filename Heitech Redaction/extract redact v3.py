# -*- coding: utf-8 -*-
"""
Created on Mon Jun 23 00:26:08 2025

@author: peace
"""


import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import fitz  # PyMuPDF
os.chdir('C:/Users/peace/Documents/GitHub/USS/Heitech Redaction/PDF assets')
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import io

def extract_pdf_fields_to_df(pdf_path: str):
    doc = fitz.open(pdf_path)
    if doc.is_encrypted:
        doc.authenticate("")  # empty password for AES-256
    data = []
    for page_num, page in enumerate(doc.pages(), start=1):
        widgets = page.widgets()
        if widgets:
            for widget in widgets:
                data.append({
                    "page": page_num,
                    "field_name": widget.field_name,
                    "field_value": widget.field_value,
                    "rect": widget.rect
                })

    df = pd.DataFrame(data)
    return df
pdf_path = "FDA-3500A_medwatch Form - Report #1216630-2025-00005.pdf"
extracted_df = extract_pdf_fields_to_df(pdf_path)


import fitz  # PyMuPDF
import pandas as pd

def flatten_v4(file_name, pages_to_apply, words_to_delete, *, extracted_df):
    doc = fitz.open(file_name)
    if doc.is_encrypted:
        doc.authenticate("")

    for page_index in pages_to_apply:
        page_num = page_index - 1
        if page_num < 0 or page_num >= len(doc):
            print(f"⚠️ Skipping invalid page number: {page_index}")
            continue

        page = doc[page_num]
        widgets = page.widgets()

        for widget in widgets:
            val = widget.field_value or ""
            if val.strip() == "":
                continue  # Skip empty fields — focus only on user input

            # Redact each word directly from the field value
            original_val = val
            for word in words_to_delete:
                def replace_case_insensitive(text, sub):
                    start = text.lower().find(sub.lower())
                    if start == -1:
                        return text
                    return text[:start] + " " * len(sub) + text[start + len(sub):]

                while word.lower() in val.lower():
                    val = replace_case_insensitive(val, word)

            if val != original_val:
                widget.field_value = val
                widget.update()  # 🔄 Ensure field is visually refreshed
                print(f"Page {page_index}: Redacted in field → '{original_val}' → '{val}'")

    #  Flatten to image-based PDF after redaction
    out = fitz.open()
    for page in doc:
        w, h = page.rect.br
        outpage = out.new_page(width=w, height=h)
        pix = page.get_pixmap(dpi=150)
        outpage.insert_image(page.rect, pixmap=pix)

    flattened_file = file_name.replace(".pdf", "_redact_flat_v4.pdf")
    out.save(flattened_file, garbage=3, deflate=True)

    print(f" Saved redacted + image-flattened PDF to: {flattened_file}")
    return flattened_file

doc = flatten_v4 (file_name="FDA MedWatch 3500A Form filled.pdf",
                    pages_to_apply=[1, 2],
                    words_to_delete=["JD123456","1989", "Blood",'Drug'],
                    extracted_df=extracted_df
                    )



import fitz  # PyMuPDF
import pandas as pd

def flatten_v5(file_name, pages_to_apply, words_to_delete, *, extracted_df):
    doc = fitz.open(file_name)
    if doc.is_encrypted:
        doc.authenticate("")

    for page_index in pages_to_apply:
        page_num = page_index - 1
        if page_num < 0 or page_num >= len(doc):
            print(f"⚠️ Skipping invalid page number: {page_index}")
            continue

        page = doc[page_num]
        widgets = page.widgets()

        for widget in widgets:
            val = widget.field_value or ""
            if val.strip() == "":
                continue  # Skip empty fields

            original_val = val
            for word in words_to_delete:
                def replace_case_insensitive(text, sub):
                    start = text.lower().find(sub.lower())
                    if start == -1:
                        return -1, text
                    return start, text[:start] + " " * len(sub) + text[start + len(sub):]

                while word.lower() in val.lower():
                    start_idx, val = replace_case_insensitive(val, word)
                    if start_idx != -1:
                        # Estimate position for black box
                        font_size = 10  # default assumed size
                        char_width = 0.5 * font_size  # rough estimate
                        x0 = widget.rect.x0 + start_idx * char_width
                        x1 = x0 + len(word) * char_width
                        redaction_rect = fitz.Rect(x0, widget.rect.y0, x1, widget.rect.y1)
                        page.draw_rect(redaction_rect, fill=(0, 0, 0), overlay=True)

            if val != original_val:
                widget.field_value = val
                widget.update()
                print(f"Page {page_index}: Redacted in field → '{original_val}' → '{val}'")

    #  Flatten to image-based PDF after redaction
    out = fitz.open()
    for page in doc:
        w, h = page.rect.br
        outpage = out.new_page(width=w, height=h)
        pix = page.get_pixmap(dpi=150)
        outpage.insert_image(page.rect, pixmap=pix)

    flattened_file = file_name.replace(".pdf", "_redact_flat_v5.pdf")
    out.save(flattened_file, garbage=3, deflate=True)

    print(f" Saved redacted + image-flattened PDF to: {flattened_file}")
    return flattened_file, out


doc , file_ftz= flatten_v5 (file_name="FDA MedWatch 3500A Form filled.pdf",
                    pages_to_apply=[1, 2],
                    words_to_delete=["JD123456","1989", "Blood",'Drug'],
                    extracted_df=extracted_df
                    )

def page_to_image(doc, page_number=0, zoom=2.0):

    if page_number < 0 or page_number >= len(doc):
        raise ValueError("Invalid page number.")
    
    page = doc.load_page(page_number)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    return image

img = page_to_image(file_ftz,1)
img.show()











