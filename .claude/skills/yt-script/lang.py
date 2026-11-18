"""lang.py - shared English + Spanish text helpers for the youtube-agent tools.

Every tool used to tokenise with [a-z], which silently drops accented letters: "último" became
"ltimo", "dólares" became "lares". These helpers keep accents and ñ, and give every tool one
place for the bilingual word lists, so a mixed title like "GTA 6: el leak de Vice City" is read
in both languages at once.

    fold(t)   lowercase, accents stripped - for matching only, never for display
    words(t)  word tokens, Unicode-aware (keeps ñ, á, ü), lowercase, accents kept
"""
import re, unicodedata

def fold(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))

WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)?")
def words(t): return WORD.findall(t.lower())

# Franchise names that carry a digit. "GTA 6" is the subject, not a statistic, so the number in it
# must not score as a concrete figure - otherwise every hook in the niche looks specific.
NAMED_NUMBER = re.compile(
    r"\b(gta|grand theft auto)\s?(vi|v|iv|6|5|4)\b|\bps\s?[345]\b|\bxbox (one|series [xs])\b|"
    r"\b(rdr|red dead( redemption)?)\s?2\b|\bswitch 2\b|\b(tr[aá]iler|trailer)\s?\d\b", re.I)
def strip_named_numbers(t): return NAMED_NUMBER.sub(" ", t)

# Function words, both languages, accent-folded. Used for title/thumbnail overlap and chapter keywords.
STOP = set("""
the a an of for to in on and or is are was were be been with this that it as at by from you your i
my we our they them he she but so if then than there here what which who how when where why not no
yes do does did just really very like about into over out up down can could will would should have
has had get got make made go going went one two
el la los las un una unos unas de del al a en y o u e que con por para es son fue era ser sido este
esta estos estas ese esa esos esas eso esto lo le les se su sus mi mis tu tus te me nos yo el ella
ellos ellas nosotros usted ustedes pero si no mas muy ya hay como cuando donde porque pues entonces
asi tambien todo toda todos todas nada algo cada otro otra otros otras sobre entre hasta desde sin
tiene tienen tener hace hacer va van vamos voy ir uno dos aqui ahi alla bien solo video videos
ahora hablemos pasemos veamos primero segundo ultimo despues luego dijo dice cosa cosas suscribete
canal like comenta comentarios final
""".split())
