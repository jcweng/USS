# -*- coding: utf-8 -*-
"""
Created on Thu Jun 19 00:02:00 2025

@author: peace
"""

# Now you can access pages, forms, etc.
# print("Decrypted PDF has", doc.page_count, "pages.")
import os
import fitz  # PyMuPDF
import pandas as pd


os.chdir('C:/Users/peace/My Drive/Python_code/PDF')

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
pdf_path = "FDA MedWatch 3500A Form filled.pdf"
extracted_df = extract_pdf_fields_to_df("FDA MedWatch 3500A Form filled.pdf")


''' this version is effect at deleting the entire fillable area and blacken it'''
def redact_pdf_fields(pdf_path: str, fields_to_redact: list[str], output_path: str = "redacted.pdf"):
    doc = fitz.open(pdf_path)
    if doc.is_encrypted:
        doc.authenticate("")

    # Step 1: Build reference of all available field names
    available_fields = set()
    field_rects = {}  # store rects for printing later

    for page in doc.pages():
        widgets = page.widgets()
        if widgets:
            for widget in widgets:
                fname = widget.field_name
                available_fields.add(fname)
                if fname in fields_to_redact:
                    field_rects[fname] = widget.rect

    # Step 2: Validate that all target fields exist
    missing_fields = [f for f in fields_to_redact if f not in available_fields]
    if missing_fields:
        raise ValueError(f"The following fields were not found in the PDF: {missing_fields}")

    # Step 3: Redact fields
    for page in doc.pages():
        widgets = page.widgets()
        if widgets:
            for widget in widgets:
               if widget.field_name in fields_to_redact:
                    rect = widget.rect
                    page.draw_rect(rect, fill=(0, 0, 0), overlay=True)
                    page.delete_widget(widget)  

    # Step 4: Print redacted region dimensions
    print("Redacted field regions (dimensions):")
    for name in fields_to_redact:
        rect = field_rects[name]
        width = rect.width
        height = rect.height
        print(f" - {name}: width={width:.2f}, height={height:.2f}, page={rect}")
    doc.save(output_path)
    
    
fields_to_blackout = ["patID", "patDOB"]
Redacted_file = "output_redacted.pdf"

redact_pdf_fields(pdf_path,
                  fields_to_blackout,
                  output_path=Redacted_file)




