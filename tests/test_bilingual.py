#!/usr/bin/env python3
"""Regression check for the bilingual (English + Spanish) tools.

    python3 tests/test_bilingual.py

Five good and five bad Spanish GTA hooks: every good one must outscore every bad one. The English
example hooks in hooks.json must still be classified as before (18 of 21).
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "yt-script"))
from hookscore import score, classify  # noqa: E402

GOOD = [
    "¿Por qué nadie está hablando del detalle de Lucia que aparece en el segundo tráiler de GTA 6?",
    "Si vas a comprar GTA 6 en PS5, no lo hagas antes de revisar estos 3 ajustes.",
    "Vi el tráiler 2 de GTA 6 cuadro por cuadro y encontré 7 detalles que casi nadie notó en Vice City.",
    "Todos dicen que el leak de GTA 6 era falso, pero hay 2 cosas que no te están contando.",
    "Te quedan 24 horas antes de que salga GTA 6 y casi nadie sabe esto de Leonida.",
]
BAD = [
    "Hola chicos, bienvenidos a un nuevo video de GTA 6, hoy vamos a hablar del juego.",
    "GTA 6 es increíble, brutal y épico, el mejor juego de la historia.",
    "Bueno, este video es básicamente sobre GTA 6.",
    "GTA 6 gameplay.",
    "En este video les voy a contar un poco de todo lo que se sabe de GTA 6, que es bastante, así que "
    "quédense hasta el final porque va a estar muy interesante y no se lo pueden perder.",
]

def main():
    g = [(score(h)[1], h) for h in GOOD]
    b = [(score(h)[1], h) for h in BAD]
    for v, h in sorted(g + b, reverse=True):
        print(f"  {'GOOD' if (v, h) in g else 'BAD '}  {v:3d}  {h[:70]}")
    worst_good, best_bad = min(v for v, _ in g), max(v for v, _ in b)
    print(f"\n  lowest good {worst_good}  vs  highest bad {best_bad}  ->  gap {worst_good - best_bad}")
    en = json.load(open(os.path.join(ROOT, "skills", "yt-script", "hooks.json"), encoding="utf-8"))["hooks"]
    n = sum(1 for f in en if classify(f["example"])[0] != "Unclassified")
    print(f"  English examples classified: {n}/21")
    ok = worst_good > best_bad and n >= 18
    print("  PASS" if ok else "  FAIL"); sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
