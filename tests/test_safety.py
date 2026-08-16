from app.tools import screen_safety


tests = [
    (
        "AC dripping with a puddle near the wall outlet",
        True,
    ),
    (
        "AC drain dripping, small puddle, no outlet near it",
        False,
    ),
    (
        "Strong smell of gas in the kitchen",
        True,
    ),
    (
        "Kitchen faucet dripping slowly",
        False,
    ),
    (
        "Ceiling light fixture fell and is hanging by the wires",
        True,
    ),
]


for text, expected in tests:
    result = screen_safety(text)

    print(text)
    print(result)
    print(f"EXPECTED HAZARD: {expected}")
    print("---")