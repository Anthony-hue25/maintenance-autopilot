from app.tools import screen_resolution_state


tests = [
    (
        "HELP the kitchen is flooding!!",
        "A bowl overflowed. No active water source remains and tenant mopped it.",
        True,
    ),
    (
        "The kitchen light was flickering.",
        "Actually it started working again, it's fine now.",
        True,
    ),
    (
        "The sink was leaking.",
        "It's still leaking under the cabinet.",
        False,
    ),
]


for request, clarification, expected in tests:
    result = screen_resolution_state(
        request,
        clarification,
    )

    print(result)
    print(f"EXPECTED close_candidate: {expected}")
    print("---")