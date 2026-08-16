from app.tools import screen_authority


tests = [
    ("U5", "Repair quoted at $240.", False),
    ("U2", "Repair quoted at $240.", True),
    ("U1", "Repair quoted at $200.", False),
    ("U4", "Repair quoted at $201.", True),
]


for unit, request, expected in tests:
    result = screen_authority(
        unit,
        request,
    )

    print(unit, request)
    print(result)
    print(
        f"EXPECTED authority_exceeded: {expected}"
    )
    print("---")