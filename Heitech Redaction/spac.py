# -*- coding: utf-8 -*-
"""
Created on Thu Jul  3 10:10:48 2025

@author: peace
"""



# python -m spacy download en_core_web_trf
import spacy
import os
os.chdir('C:/Users/peace/My Drive/Python_code/Redactions')
    file_object = open("your_file.txt", "r")

# Load the pre-trained model
nlp = spacy.load('en_core_web_trf')

# Process a text
doc = nlp("Barack Obama was born on August 4, 1961, in Honolulu, Hawaii.")



doc = nlp("We arrived at 2151 E Grand Ave, WOODBURY, TX 78543")

# Extract and print named entities
for ent in doc.ents:
    print(ent.text, ent.label_)


import 