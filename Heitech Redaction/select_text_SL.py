import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")
st.title("Text Highlighter")

uploaded_file = st.file_uploader("Upload a text file", type=["txt"])

if uploaded_file:
    text = uploaded_file.read().decode("utf-8")
    words = text.split()
    word_html = " ".join([f"<span class='word'>{w}</span>" for w in words])

    components.html(f"""
    <html>
    <head>
    <style>
        body {{
            font-family: sans-serif;
            font-size: 12px;
        }}
        .button-container {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .highlight-btn {{
            border: none;
            padding: 8px 16px;
            margin: 0 10px;
            border-radius: 10px;
            cursor: pointer;
            color: black;
            font-weight: bold;
            font-size: 14px;
        }}
        #B2 {{ background-color: gold; }}
        #B4 {{ background-color: dodgerblue; }}

        .text-box {{
            border: 1px solid #ccc;
            border-radius: 10px;
            padding: 15px;
            background-color: #f9f9f9;
            line-height: 1.8;
        }}

        .word {{
            display: inline;
            margin: 1px;
            padding: 2px 4px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
    </style>
    </head>
    <body>
        <div class="button-container">
            <button class="highlight-btn" id="B2" onclick="setColor('gold')">B2</button>
            <button class="highlight-btn" id="B4" onclick="setColor('dodgerblue')">B4</button>
        </div>

        <div class="text-box" id="text-box">
            {word_html}
        </div>

        <script>
        let currentColor = 'gold';

        function setColor(color) {{
            currentColor = color;
        }}

        document.querySelectorAll('.word').forEach(word => {{
            word.addEventListener('click', () => {{
                const currentBG = word.style.backgroundColor;
                if (currentBG === currentColor || currentBG === rgbConvert(currentColor)) {{
                    word.style.backgroundColor = '';
                    word.style.color = '';
                }} else {{
                    word.style.backgroundColor = currentColor;
                    word.style.color = 'black';
                }}
            }});
        }});

        function rgbConvert(colorName) {{
            const dummy = document.createElement("div");
            dummy.style.color = colorName;
            document.body.appendChild(dummy);
            const rgb = getComputedStyle(dummy).color;
            document.body.removeChild(dummy);
            return rgb;
        }}
        </script>
    </body>
    </html>
    """, height=400, scrolling=True)
