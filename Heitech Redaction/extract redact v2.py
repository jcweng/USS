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
import numpy as np
import matplotlib.pyplot as plt


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

print(str(extracted_df['field_value'][extracted_df['field_name'] == 'advEvDescribe']))

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

'''
Blacken the right area, but can still see through.
'''

def redact_v2(file_name, pages_to_apply, words_to_delete):
    doc = fitz.open(file_name)
    if doc.is_encrypted:
        doc.authenticate("")

    output_file = file_name.replace(".pdf", "_redact_v2.pdf")

    for page_index in pages_to_apply:
        page_num = page_index - 1
        if page_num < 0 or page_num >= len(doc):
            print(f"⚠️ Skipping invalid page number: {page_index}")
            continue

        page = doc[page_num]
        widgets = page.widgets()

        for word in words_to_delete:
            matches = page.search_for(word, quads=False)

            for match_rect in matches:
                for widget in widgets:
                    val = widget.field_value or ""
                    if word.lower() in val.lower() and widget.rect.contains(match_rect):
                        # Draw redaction box
                        page.draw_rect(match_rect, fill=(0, 0, 0), overlay=True)

                        # Replace matched phrase in field_value with spaces
                        def replace_case_insensitive(text, sub):
                            start = text.lower().find(sub.lower())
                            if start == -1:
                                return text
                            return text[:start] + " " * len(sub) + text[start+len(sub):]

                        new_val = val
                        while word.lower() in new_val.lower():
                            new_val = replace_case_insensitive(new_val, word)

                        widget.field_value = new_val

                        print(f"Page {page_index}: Redacted '{word}' inside field '{getattr(widget, 'name', 'unknown')}', replaced in value: '{val}' → '{new_val}'")
                        break  # Stop at first match field
    return doc, output_file

doc, output_path = redact_v2(
    file_name="FDA MedWatch 3500A Form filled.pdf",
    pages_to_apply=[1, 2],
    words_to_delete=["JD123456","1989", "Blood",'Drug']
)

doc.save('FDA MedWatch 3500A Form redacted.pdf')




''' this version flatten the file. this drived from redact_v2, have issue with not redacting phrases in longer description box'''

import os
import fitz  # PyMuPDF
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
os.chdir('C:/Users/peace/My Drive/Python_code/PDF')


def flatten_v2(file_name, pages_to_apply, words_to_delete):
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

        for word in words_to_delete:
            matches = page.search_for(word, quads=False)
            for match_rect in matches:
                for widget in widgets:
                    val = widget.field_value or ""
                    if word.lower() in val.lower() and widget.rect.contains(match_rect):
                        # Draw black redaction box
                        page.draw_rect(match_rect, fill=(0, 0, 0), overlay=True)

                        # Replace redacted phrase with spaces
                        def replace_case_insensitive(text, sub):
                            start = text.lower().find(sub.lower())
                            if start == -1:
                                return text
                            return text[:start] + " " * len(sub) + text[start + len(sub):]

                        new_val = val
                        while word.lower() in new_val.lower():
                            new_val = replace_case_insensitive(new_val, word)

                        widget.field_value = new_val

                        print(f"Page {page_index}: Redacted '{word}' in field → '{val}' → '{new_val}'")
                        break  # stop after matching widget

 # ✅ Display the first page
    page = doc[0]
    zoom = 4.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    dpi = 100
    fig_w, fig_h = pix.width / dpi, pix.height / dpi
    plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    plt.imshow(image)
    plt.axis("off")
    plt.title("First Page Preview")
    plt.show()
    
    # ✅ Final step: flatten all form fields into static content
    # doc.flatten_forms()
    
    # ✅ Now flatten by rendering to image-based PDF
    out = fitz.open()
    for page in doc:
        w, h = page.rect.br
        outpage = out.new_page(width=w, height=h)
        pix = page.get_pixmap(dpi=150)
        outpage.insert_image(page.rect, pixmap=pix)

    flattened_file = file_name.replace(".pdf", "_redact_flat_v2.pdf")
    out.save(flattened_file, garbage=3, deflate=True)    
    
    print(f"✅ Saved redacted + image-flattened PDF to: {flattened_file}")
    return flattened_file

doc = flatten_v2 (file_name="FDA MedWatch 3500A Form filled.pdf",
    pages_to_apply=[1, 2],
    words_to_delete=["JD123456","1989", "Blood",'Drug']
    )













