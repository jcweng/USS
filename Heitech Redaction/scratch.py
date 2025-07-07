# -*- coding: utf-8 -*-
"""
Created on Thu Jul  3 08:23:43 2025

@author: peace
"""

import pandas as pd
from pandasai import SmartDataframe
from pandasai.llm.openai import OpenAI


# client = OpenAI(api_key="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")
GPT_MODEL = "gpt-3.5-turbo" #"gpt-3.5-turbo-1106"

# Sample DataFrame
df = pd.DataFrame({
    "Name": ["alice", "bob", "charlie"],
    "Age": [25, 30, 35],
    "Department": ["sales", "engineering", "marketing"]
})

# Initialize the LLM (you need your OpenAI API key configured via environment variable or directly)
llm = OpenAI(api_token="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")  # or leave blank if already set via env

# Wrap DataFrame in SmartDataframe
sdf = SmartDataframe(df, config={"llm": llm})

# Ask PandasAI to format it — for example: capitalize names and departments
formatted_df = sdf.chat("Capitalize all values in the 'Name' and 'Department' columns and return the updated dataframe.")

# Output the result
print(formatted_df)
