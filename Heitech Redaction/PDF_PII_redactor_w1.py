import os
import fitz
import spacy
import pandas as pd
import re

# Step 1: Open PDF and extract form fields
os.chdir('C:/Users/peace/Documents/GitHub/USS/Heitech Redaction/PDF assets')
pdf_path = "FDA-3500A_medwatch Form - Report #2049312-2025-00005.pdf"

# Load spaCy and custom patterns
nlp = spacy.load("en_core_web_trf")
ruler = nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})
patterns = [
    # Address patterns
    {
        "label": "ADDRESS",
        "pattern": [
            {"TEXT": {"REGEX": r"^\d{3,6}$"}},
            {"IS_ALPHA": True, "OP": "+"},
            {"IS_ALPHA": True, "OP": "?"},
            {"IS_ALPHA": True, "OP": "+"},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_ALPHA": True, "LENGTH": 2},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_DIGIT": True, "LENGTH": 5}
        ]
    },
    {
        "label": "ADDRESS",
        "pattern": [
            {"IS_DIGIT": True},
            {"IS_ALPHA": True, "OP": "?"},
            {"IS_ALPHA": True},
            {"IS_ALPHA": True, "OP": "?"},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_ALPHA": True},
            {"IS_PUNCT": True, "OP": "?"},
            {"IS_ALPHA": True, "LENGTH": 2},
            {"IS_DIGIT": True, "LENGTH": 5}
        ]
    },
    # Date pattern
    {
        "label": "DATE",
        "pattern": [
            {"IS_DIGIT": True},
            {"LOWER": {"REGEX": "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"}},
            {"IS_DIGIT": True}
        ]
    },
    # SSN patterns
    {
      "label": "SSN",
      "pattern": [
        {"TEXT": {"REGEX": r"^\d{3}[-\s]?\d{2}[-\s]?\d{4}$"}}
      ]
    },
    {
      "label": "SSN",
      "pattern": [
        {"TEXT": {"REGEX": r"^\d{3}$"}},
        {"TEXT": "-"},
        {"TEXT": {"REGEX": r"^\d{2}$"}},
        {"TEXT": "-"},
        {"TEXT": {"REGEX": r"^\d{4}$"}}
      ]
    }
 
]
ruler.add_patterns(patterns)

# Data collection for reporting
results = []

# Open PDF
doc = fitz.open(pdf_path)
redaction_count = 0
unmatched = []

data = []
for page_num, page in enumerate(doc, start=1):
    widgets = page.widgets()
    if widgets:
        for widget in widgets:
            data.append({
                "Page": page_num,
                "Field Name": widget.field_name,
                "Field Value": widget.field_value,
                "Field Type": widget.field_type,
                "Rect": widget.rect
            })

widgets_df = pd.DataFrame(data)
widgets_df = widgets_df.dropna(subset=['Field Value'])
widgets_df = widgets_df[~widgets_df['Field Value'].astype(str).str.strip().isin(['', '0', '--'])]

for page_num, page in enumerate(doc):
    widgets = page.widgets()
    if not widgets:
        continue

    for widget in widgets:
        if widget.field_type != fitz.PDF_WIDGET_TYPE_TEXT or not widget.field_value:
            continue

        original_value = widget.field_value
        normalized_value = re.sub(r"\s+", " ", original_value.replace("\n", " ").strip())
        redacted_value = normalized_value
        field_doc = nlp(normalized_value)

        has_address = any(e.label_ == "ADDRESS" for e in field_doc.ents)

        for ent in field_doc.ents:
            if ent.label_ in {"CARDINAL", "QUANTITY"}:
                continue
            if ent.label_ in {"FAC", "GPE"} and has_address:
                continue
            if ent.label_ == "PERSON" and any(char.isdigit() for char in ent.text):
                continue
            if ent.label_ == "DATE":
                if len(ent.text.strip()) == 1 or not re.search(r"\b(19|20)\d{2}\b", ent.text.lower()):
                    continue

            total_len = len(ent.text)
            pad = max(0, total_len - len(ent.label_) - 2)
            left_pad = pad // 2
            right_pad = pad - left_pad
            replacement = f"{' ' * left_pad}[{ent.label_}]{' ' * right_pad}"

            if ent.text in redacted_value:
                redacted_value = redacted_value.replace(ent.text, replacement)
                redaction_count += 1
                results.append({
                    "Page": page_num + 1,
                    "Field Name": widget.field_name,
                    "Original Text": ent.text,
                    "Label": ent.label_,
                    "Redacted": True
                })
            else:
                unmatched.append((page_num + 1, widget.field_name, ent.text, ent.label_))
                results.append({
                    "Page": page_num + 1,
                    "Field Name": widget.field_name,
                    "Original Text": ent.text,
                    "Label": ent.label_,
                    "Redacted": False
                })

        widget.field_value = redacted_value
        widget.update()

# Save and close PDF
output_path = "redacted_output.pdf"
doc.save(output_path)
doc.close()

# Display summary
print(f"Redacted PDF saved to: {output_path}")
print(f"Redactions applied: {redaction_count}")

# Create and display DataFrame
results_df = pd.DataFrame(results)
# print("\nDetected Entities Summary:")
# print(results_df)

if unmatched:
    print("\nUnmatched Redaction Targets:")
    for entry in unmatched:
        print(f"Page {entry[0]} | Field: {entry[1]} | Label: {entry[3]} | Text: {entry[2]}")
