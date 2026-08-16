from app.tools import screen_security_information


tests = [
    (
        "The front door lock is being weird.",
        "No response to: Can you still lock and secure the door?",
        False,
        True,
    ),
    (
        "Just letting you know whenever someone's free, "
        "the second bedroom window doesn't latch shut properly.",
        "",
        True,
        False,
    ),
    (
        "Front door handle came off in my hand, door still locks though.",
        "",
        False,
        False,
    ),
    (
        "Window won't lock, it's the ground floor one facing the street.",
        "",
        False,
        False,
    ),
]


for request, clarification, expected_ask, expected_silence in tests:
    result = screen_security_information(
        request,
        clarification,
    )

    print(request)
    print(result)
    print(f"EXPECTED needs_clarification: {expected_ask}")
    print(f"EXPECTED safety_silence: {expected_silence}")
    print("---")