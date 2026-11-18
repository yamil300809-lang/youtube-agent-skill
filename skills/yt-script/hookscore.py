#!/usr/bin/env python3
"""hookscore.py - score a YouTube hook before you waste a take on it.

Five properties, 0-100 each, and a verdict that is 60% the mean and 40% the weakest one. The
weakest-link weighting is deliberate: a hook with four strong properties and one dead one is a hook
that leaks at the dead one, and averaging hides that.

    python3 hookscore.py hooks.txt            # one hook per line, ranked
    python3 hookscore.py --hook "one line"    # score a single hook
    python3 hookscore.py --json hooks.txt     # machine-readable

WHAT THIS CAN AND CANNOT TELL YOU. Measured against 74 real short-form hooks (first 15 seconds of
auto-captions, top-8 and bottom-8 by views across five channels): it separates deliberately bad
hooks from real ones well, and it separates a creator's own hits from their own misses barely at
all. Treat a low score as a reason to look again, never a high score as a promise.

Bilingual: English and Spanish are read at once, accents optional, so mixed titles like
"el leak de Vice City" score on both. "GTA 6" and similar names are not counted as statistics.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lang import fold, words as lang_words, strip_named_numbers  # noqa: E402
FORMULAS = json.load(open(os.path.join(HERE, "hooks.json"), encoding="utf-8"))["hooks"]

# Bilingual (English + Spanish). Every set and pattern below is matched against fold(t): lowercase,
# accents stripped, so "increíble" and "increible" are the same word. GTA titles mix both languages
# ("el leak de Vice City"), so both lists always run - there is no language switch to get wrong.
FILLER = {"basically","actually","literally","just","really","very","so","kind","sort","like",
          "guys","hey","welcome","today","video","subscribe","channel",
          "basicamente","literalmente","realmente","muy","bueno","pues","hola","chicos","chavos",
          "gente","amigos","bienvenidos","bienvenido","hoy","suscribete","canal","nuevo","tipo",
          "bastante","poquito"}
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","game","changer","secret",
         "powerful","ultimate","best","revolutionary","mind","blowing","unbelievable","epic",
         "increible","brutal","loco","locura","epico","enorme","mejor","impresionante","bestial",
         "impactante","espectacular","genial","perfecto","historia","bonito","interesante"}
CONCRETE = re.compile(r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year|"
                      r"segundo|minuto|hora|dia|semana|mes|ano)(s|es)?|\d+\s?(mil|millones))\b", re.I)
YOU = re.compile(r"\b(you|your|you're|youre|yourself|"
                 r"tu|tus|te|ti|contigo|usted|ustedes|vos|les|sabias|viste|imagina|mira|fijate|"
                 r"crees|quieres|puedes|tienes|vas|estas|eres|juegas|necesitas|sigues)\b", re.I)
STAKE = re.compile(r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead|"
                   r"perder|pierdes|perderte|perdiste|perdido|desperdicias?|cuesta|cuestan|costar|riesgo|"
                   r"antes|nunca|jamas|deja de|dejes|error|errores|cuidado|caro|pagar|pagas|retraso|"
                   r"retrasado|retrasan|cancelad[oa]|ban|baneo|baneado|borrad[oa]|muere|tarde|"
                   r"no (lo |la )?(compres|hagas|juegues|reserves|gastes))\b", re.I)
# "como" and "que" are everyday words in Spanish; only the accented question forms (cómo, qué...)
# and an opening "¿" count, so those are checked on the original text, not the folded one.
CURIOSITY = re.compile(r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually|"
                       r"por que|antes|hasta|pero|nadie|casi|excepto|salvo|razon|en realidad|la verdad|"
                       r"de verdad|todavia|aun)\b", re.I)
CURIOSITY_ES = re.compile(r"(?<!\w)(qué|cómo|cuál|cuáles|cuándo|dónde|quién|quiénes|cuánto|cuánta)(?!\w)|¿", re.I)
CLOSED = re.compile(r"\b(because|so that|which means|porque|asi que|lo que significa|es decir|o sea)\b", re.I)

def words(t): return lang_words(t)

def specificity(t):
    w = [fold(x) for x in words(t)]
    if not w: return 0
    nums = len(CONCRETE.findall(fold(strip_named_numbers(t))))
    vague = sum(1 for x in w if x in VAGUE)
    filler = sum(1 for x in w if x in FILLER)
    s = 34 + nums * 22 - vague * 16 - filler * 5
    # proper nouns that are not sentence-initial read as named things (Leonida, Vice City, Lucia)
    s += min(18, 6 * sum(1 for x in t.lstrip("¿¡").split()[1:] if x.lstrip("¿¡\"'(")[:1].isupper()))
    return max(0, min(100, s))

def address(t):
    f = fold(t)
    n = len(YOU.findall(f))
    first = 30 if YOU.search(" ".join(f.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))

def stakes(t):
    f = fold(t)
    n = len(STAKE.findall(f))
    return max(0, min(100, 22 + n * 26 + (14 if CONCRETE.search(fold(strip_named_numbers(t))) else 0)))

def curiosity(t):
    n = len(CURIOSITY.findall(fold(t))) + len(CURIOSITY_ES.findall(t.lower()))
    q = 18 if t.strip().endswith("?") else 0
    # a hook that resolves itself has no gap left
    closed = -18 if CLOSED.search(fold(t)) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))

def brevity(t):
    n = len(words(t))
    if n == 0: return 0
    # 9-24 words is the band a spoken hook lands in at ~150wpm inside 10 seconds. Spanish runs a few
    # words longer for the same idea, so the top of the band stretches to 28 for it.
    hi = 28 if re.search(r"[áéíóúñ¿¡]| (el|la|de|que|los|las) ", t.lower()) else 24
    if 9 <= n <= hi: return 100
    if n < 9:  return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - hi) * 7)

PROPS = [("SPECIFICITY", specificity), ("ADDRESS", address), ("STAKES", stakes),
         ("CURIOSITY", curiosity), ("BREVITY", brevity)]

def classify(t):
    best, hits, ft = None, 0, fold(t)
    for f in FORMULAS:
        n = sum(1 for p in f["match"] if re.search(p, t, re.I) or re.search(p, ft, re.I))
        if n > hits: best, hits = f, n
    return (best["name"] if best else "Unclassified"), hits

def score(t):
    parts = {n: fn(t) for n, fn in PROPS}
    vals = list(parts.values())
    verdict = round(0.6 * (sum(vals) / len(vals)) + 0.4 * min(vals))
    name, hits = classify(t)
    return parts, verdict, name, hits

def band(v): return "STRONG" if v >= 72 else "WORKABLE" if v >= 55 else "WEAK"

def report(t, parts, verdict, name, hits):
    print(f"\n  {t.strip()}")
    print(f"  {'-' * min(72, max(20, len(t.strip())))}")
    for k, v in parts.items():
        print(f"    {k:<12} {v:3d}  {'#' * (v // 5)}")
    print(f"    {'VERDICT':<12} {verdict:3d}  {band(verdict)}")
    print(f"    formula      {name}" + (f"  ({hits} pattern{'s' if hits != 1 else ''} matched)" if hits else "  (no formula matched - that is usually a summary, not a hook)"))
    low = min(parts, key=parts.get)
    print(f"    weakest      {low} - {FIX[low]}")

FIX = {
 "SPECIFICITY": "swap one adjective for a number, a name or a date",
 "ADDRESS": "say 'you' / 'tú' in the first six words",
 "STAKES": "name what it costs them to keep doing it the current way",
 "CURIOSITY": "cut the half of the sentence that answers itself",
 "BREVITY": "9 to 24 words. Read it out loud and stop where you run out of breath",
}

def main():
    a = sys.argv[1:]
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    if "--hook" in a:
        lines = [a[a.index("--hook") + 1]]
    elif a and os.path.exists(a[0]):
        lines = [l for l in open(a[0], encoding="utf-8").read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1 if not a else 0)
    out = []
    for t in lines:
        parts, verdict, name, hits = score(t)
        out.append({"hook": t.strip(), "properties": parts, "verdict": verdict,
                    "band": band(verdict), "formula": name, "matched": hits})
    out.sort(key=lambda r: -r["verdict"])
    if as_json:
        print(json.dumps([{k: v for k, v in r.items() if k != "matched"} for r in out], indent=1, ensure_ascii=False)); return
    for r in out:
        report(r["hook"], r["properties"], r["verdict"], r["formula"], r["matched"])
    if len(out) > 1:
        print(f"\n  winner: {out[0]['hook'].strip()}  ({out[0]['verdict']}, {out[0]['band']})\n")

if __name__ == "__main__":
    main()
