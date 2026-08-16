from app.tools import (
    screen_information_state,
    screen_scope_change,
)


print("TEST 1 — unresolved clarification")
result = screen_information_state(
    "There's a damp patch on the ceiling.",
    "I don't know, it's just there. Can't see any leak. "
    "It was maybe there before too, not sure.",
)
print(result)
print("EXPECTED: insufficient_after_ask = True")
print("---")


print("TEST 2 — useful clarification")
result = screen_information_state(
    "There's water on the kitchen floor.",
    "It's under the sink near the garbage disposal. "
    "No outlets nearby and it stops when I don't run the disposal.",
)
print(result)
print("EXPECTED: insufficient_after_ask = False")
print("---")


print("TEST 3 — hidden-damage scope change")
result = screen_scope_change(
    "The bathroom sink is draining slowly and there's a musty smell. "
    "The wall under the sink feels soft and there's dark staining."
)
print(result)
print("EXPECTED: scope_change_detected = True")
print("---")


print("TEST 4 — simple drain issue")
result = screen_scope_change(
    "The bathroom sink is draining slowly."
)
print(result)
print("EXPECTED: scope_change_detected = False")
print("---")