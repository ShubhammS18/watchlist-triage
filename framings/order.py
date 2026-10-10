"""Field order. A block is every item of one kind, in the order the alert lists them.

    framing 2   watchlist block, customer block, notes; items inside each block keep their order
    framing 3   notes in their order, customer block reversed, watchlist block reversed
"""
# framing -> ((kind, reversed?), ...) in the order the blocks are shown
BLOCKS = {
    2: (("watchlist_field", False), ("customer_field", False), ("snippet", False)),
    3: (("snippet", False), ("customer_field", True), ("watchlist_field", True)),
}


def reorder(items, framing):
    """The same items in the order framing 1, 2 or 3 shows them."""
    if framing == 1:
        return list(items)
    ordered = []
    for kind, backwards in BLOCKS[framing]:
        block = [item for item in items if item["kind"] == kind]
        ordered += reversed(block) if backwards else block
    if len(ordered) != len(items):
        raise ValueError(f"an item has a kind outside {[kind for kind, _ in BLOCKS[framing]]}")
    return ordered
