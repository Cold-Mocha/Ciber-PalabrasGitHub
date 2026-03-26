# Normaliza identificadores y los divide en palabras individuales

import re


def extract_words_from_identifier(identifier: str) -> list[str]:
    if not identifier:
        return []

    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', identifier)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    s3 = s2.replace('-', '_')
    words = s3.split('_')

    clean_words = [word.lower() for word in words if word.strip() and not word.isdigit()]
    return clean_words