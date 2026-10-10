"""Name formats. Tokens are reordered and re-punctuated by position only: no guess at given or family name.

Titles and accents stay as written. A title is a first token that is in the title list once its dot is removed.

    framing 1   Dr Drigutek Plukil      as written
    framing 2   Dr. PLUKIL, Drigutek    title with a dot, last token in capitals, comma, the other tokens in order
    framing 3   Dr Plukil Drigutek      title without a dot, last token first, the other tokens in order
"""
from worldgen.textutil import normalise, strip_diacritics


def _letters(text):
    return strip_diacritics(normalise(text))


def format_name(name, framing, titles=frozenset()):
    """`name` as framing 1, 2 or 3 writes it. `titles` holds lower-case titles without dots.

    Raises ValueError rather than guess: when the name has fewer than two tokens after the title, and when
    capitals would change the name's normalised letters (for example a letter whose capital is two letters).
    """
    if framing == 1:
        return name
    tokens = name.split(" ")
    title = tokens[:1] if tokens[0].rstrip(".").lower() in titles else []
    rest = tokens[len(title):]
    if len(rest) < 2 or "" in tokens:
        raise ValueError(f"cannot reorder the name {name!r}: it needs two or more tokens after the title")
    *others, last = rest
    if framing == 2:
        if _letters(last.upper()) != _letters(last):
            raise ValueError(f"capitals would change the letters of {last!r} in the name {name!r}")
        return " ".join([t.rstrip(".") + "." for t in title] + [last.upper() + ","] + others)
    return " ".join([t.rstrip(".") for t in title] + [last] + others)
