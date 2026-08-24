"""Generate rgba() fallbacks for Tailwind v4 opacity modifiers.

Tailwind v4 compiles `bg-success/20` as:

    .bg-success\/20 { background-color: var(--success) }        <- fallback, FULLY OPAQUE
    @supports (color:color-mix(in lab,red,red)) { ...20%... }

Browsers without color-mix() (Safari < 16.2) take that fallback, so every tinted
pill paints at full opacity and text coloured from the same token disappears.

Tailwind cannot do better: it only has `var(--token)`, and CSS can't decompose a
custom property into rgba channels. At generation time we know the hex, so we can
emit real rgba() -- supported universally, correct over any backdrop, and correct
for overlays that must stay see-through.
"""
import glob, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent  # frontend/
BUILT = sorted(glob.glob(str(ROOT / "dist" / "assets" / "*.css")))[0]
SRC = (ROOT / "src" / "index.css").read_text(encoding="utf-8")

def palette(block):
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});", block))

LIGHT = palette(SRC[SRC.index(":root"):SRC.index('[data-theme="dark"]')])
DARK  = palette(SRC[SRC.index('[data-theme="dark"]'):])
DARK  = {**LIGHT, **DARK}          # dark inherits any token it doesn't restate
LIGHT["white"] = DARK["white"] = "#ffffff"

def rgba(hex_, a):
    h = hex_.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a:g})"

css = open(BUILT, encoding="utf-8").read()
found = re.findall(
    r"([^{}]*?\/\d+)\{(background-color|color|--tw-ring-color):var\(--([a-z0-9-]+)\)\}"
    r"@supports \(color:color-mix", css)

rules, skipped = {"light": [], "dark": []}, set()
for sel_group, prop, tok in sorted(set(found)):
    # Tailwind groups the bare class with its lowest-opacity variant
    # (".bg-ink,.bg-ink\/40"). Only the /N selectors get an alpha.
    for sel in (s for s in sel_group.split(",") if "\/" in s):
        alpha = int(re.search(r"\/(\d+)$", sel).group(1)) / 100
        for theme, pal in (("light", LIGHT), ("dark", DARK)):
            if tok not in pal:
                skipped.add((sel, tok)); continue
            rules[theme].append(f"  {sel}{{{prop}:{rgba(pal[tok], alpha)}}}")

same = [l for l, d in zip(rules["light"], rules["dark"]) if l == d]
print("\n".join([
 "/*",
 " * Opacity fallbacks for browsers without color-mix() (Safari < 16.2 / iPadOS <= 16.1).",
 " *",
 " * Tailwind v4 emits `background-color: var(--token)` as the fallback for every",
 " * `/opacity` utility, guarded by `@supports (color: color-mix(...))`. Without that",
 " * support the fallback paints the token at FULL opacity, so any pill whose text comes",
 " * from the same token renders invisibly -- Badge `neutral` is bg-text-muted/15 +",
 " * text-text-muted, i.e. grey on identical grey; FormBadge is green on green.",
 " *",
 " * Tailwind can't emit rgba() itself because it only has `var(--token)` and CSS cannot",
 " * decompose a custom property into channels. We know the hex here, so we can. rgba()",
 " * is universally supported and stays translucent, which matters for overlays.",
 " *",
 " * GENERATED -- after adding new `/opacity` utilities, re-run:",
 " *   npx vite build && python scripts/gen_color_mix_fallback.py",
 " */",
 "@supports not (color: color-mix(in lab, red, red)) {",
 *rules["light"], "",
 *[f'  [data-theme="dark"] {r.strip()}' for r in rules["dark"]],
 "}"]))
print(f"/* light={len(rules['light'])} dark={len(rules['dark'])} identical={len(same)} skipped={sorted(skipped)} */", file=sys.stderr)
