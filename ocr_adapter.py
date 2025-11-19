import os

def extract_text_from_image(path: str):
    base = os.path.basename(path)
    name = os.path.splitext(base)[0]
    tokens = []
    tokens.append(name)
    tokens.extend(name.replace('-', ' ').replace('_', ' ').split())
    return tokens
