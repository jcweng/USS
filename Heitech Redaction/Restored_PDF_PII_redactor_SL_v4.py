[...TRUNCATED FOR DISPLAY... See downloadable file for full content...]

# === Combined Text Correction Function ===
def apply_text_corrections(text, spell_level, grammar_level, fluency_level):
    if spell_level == "disable" and grammar_level == "disable" and fluency_level == "disable":
        return text

    prompt = text
    from spellchecker import SpellChecker
    import spacy
    import contextualSpellCheck
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Apply spelling correction
    if spell_level == "1":
        spell = SpellChecker()
        words = prompt.split()
        prompt = " ".join([spell.correction(word) or word for word in words])

    # Apply grammar correction
    if grammar_level == "1":
        nlp = spacy.load("en_core_web_sm")
        contextualSpellCheck.add_to_pipe(nlp)
        doc = nlp(prompt)
        prompt = doc._.outcome_spellCheck

    # Apply fluency and OpenAI correction (any '3' triggers GPT-3.5)
    if "3" in [spell_level, grammar_level, fluency_level]:
        system_instruction = "Correct the grammar, spelling, and fluency of the following text."
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()

    return prompt
