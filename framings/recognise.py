"""Which original wording a snippet is, from its text alone.

Every template in worldgen.snippets is rendered with the alert's own two names and compared with the text. No
other source is consulted: a snippet's tag is never read from the world.
"""
from worldgen.snippets import INJECTED_TEXTS, TEMPLATES

INJECTED = frozenset(text for _, text in INJECTED_TEXTS)


def which_original(text, customer_name, listed_name):
    """(tag, index) of the one template that renders to `text`, or None when `text` is one of the injected texts.

    Raises ValueError when more than one template matches, and when nothing matches and the text is not injected.
    """
    found = [(tag, index) for tag, templates in TEMPLATES.items() for index, template in enumerate(templates)
             if template.format(c=customer_name, w=listed_name) == text]
    if len(found) > 1:
        raise ValueError(f"snippet matches {len(found)} templates: {text!r}")
    if found:
        return found[0]
    if text in INJECTED:
        return None
    raise ValueError(f"snippet matches no template and is not an injected text: {text!r}")
