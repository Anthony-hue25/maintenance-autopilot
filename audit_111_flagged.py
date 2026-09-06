import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "audit_111_outputs.html"
OUT = ROOT / "audit_111_flagged.html"


document = SOURCE.read_text(
    encoding="utf-8"
)


# Find every complete case card.
cards = re.findall(
    r'<article class="([^"]*)">(.*?)</article>',
    document,
    flags=re.DOTALL
)


flagged_cards = []

for classes, body in cards:
    class_names = classes.split()

    if "flagged" in class_names:
        flagged_cards.append(
            f'<article class="{classes}">'
            f'{body}'
            f'</article>'
        )


if not flagged_cards:
    raise RuntimeError(
        "No flagged cases were found."
    )


# Extract the original style block so the
# flagged report looks exactly like the full audit.
style_match = re.search(
    r"<style>(.*?)</style>",
    document,
    flags=re.DOTALL
)

style = (
    style_match.group(1)
    if style_match
    else ""
)


output = f"""<!doctype html>
<html lang="en">

<head>
<meta charset="utf-8">

<meta
  name="viewport"
  content="width=device-width, initial-scale=1"
>

<title>
Maintenance Autopilot — Flagged Cases
</title>

<style>
{style}
</style>
</head>

<body>

<header>
  <h1>
    Maintenance Autopilot — Flagged Cases
  </h1>

  <p>
    Manual review of the remaining
    auto-flagged human-facing outputs.
  </p>

  <div class="summary">
    <span>
      {len(flagged_cards)} cases to review
    </span>
  </div>
</header>

<main>
{''.join(flagged_cards)}
</main>

</body>
</html>
"""


OUT.write_text(
    output,
    encoding="utf-8"
)


print()
print("Flagged-only audit created")
print("--------------------------")
print(
    f"Cases:  {len(flagged_cards)}"
)
print(
    f"Report: {OUT}"
)