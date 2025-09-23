import sqlite3
from typing import Sequence
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Stopwords españolas (como LISTA, no set)
SPANISH_STOPWORDS = [
    "a","al","algo","algunas","algunos","ante","antes","aquel","aquella","aquellas","aquellos","aqui",
    "asi","aun","aunque","bajo","bien","cada","como","con","contra","cual","cuales","cuando","de","del",
    "desde","donde","dos","durante","e","el","ella","ellas","ello","ellos","en","entre","era","erais",
    "eramos","eran","eres","es","esa","esas","ese","eso","esos","esta","estaba","estabais","estabamos",
    "estaban","estoy","estas","este","esto","estos","fin","fue","fueron","fuimos","ha","haber","habia",
    "habiais","habiamos","habian","habra","habran","habria","habrian","han","hasta","hay","haya","he",
    "hemos","hizo","la","las","le","les","lo","los","mas","me","mi","mis","mucho","muy","nada","ni","no",
    "nos","nosotras","nosotros","nuestra","nuestras","nuestro","nuestros","o","os","otra","otras","otro",
    "otros","para","pero","poco","por","porque","que","quien","quienes","se","sea","sean","segun","ser",
    "si","siempre","sin","sobre","sois","solamente","solo","somos","son","soy","su","sus","tal","tambien",
    "tampoco","te","ti","tiene","tienen","toda","todas","todavia","todo","todos","tu","tus","tuya","tuyo",
    "un","una","uno","unos","usted","ustedes","va","vamos","van","vosotras","vosotros","y","ya"
]

def _tfidf_cosine(texts: Sequence[str]) -> float:
    """
    Calcula similitud coseno entre dos textos con TF-IDF.
    Maneja casos vacíos o vocabulario vacío.
    """
    a = (texts[0] or "").strip()
    b = (texts[1] or "").strip()
    if not a and not b:
        return 0.0
    # Si uno está vacío y el otro no, la similitud queda 0
    if not a or not b:
        return 0.0

    vec = TfidfVectorizer(
        stop_words=SPANISH_STOPWORDS,
        lowercase=True,
        strip_accents="unicode"
    )
    try:
        X = vec.fit_transform([a, b])
    except ValueError:
        # e.g. "empty vocabulary; perhaps the documents only contain stop words"
        return 0.0

    sim = float(cosine_similarity(X[0], X[1])[0, 0])
    if sim < 0:
        sim = 0.0
    if sim > 1:
        sim = 1.0
    return sim

def compare_texts(a: str, b: str) -> float:
    return _tfidf_cosine([a, b])

def compare_course_ids(con: sqlite3.Connection, id_a: int, id_b: int) -> float:
    sql = "SELECT title, description, value_proposal, tutoria FROM courses WHERE course_id=?"
    def get_text(cid: int) -> str:
        row = con.execute(sql, (cid,)).fetchone()
        if not row:
            return ""
        title, desc, vp, tut = row
        return " ".join([t for t in (title, desc, vp, tut) if t])
    return compare_texts(get_text(id_a), get_text(id_b))

# Opcional: comparar por URL o por “contiene en título”
def compare_course_urls(con: sqlite3.Connection, url_a: str, url_b: str) -> float:
    ra = con.execute("SELECT course_id FROM courses WHERE url=?", (url_a,)).fetchone()
    rb = con.execute("SELECT course_id FROM courses WHERE url=?", (url_b,)).fetchone()
    if not ra or not rb:
        return 0.0
    return compare_course_ids(con, ra[0], rb[0])

def compare_course_titles_contains(con: sqlite3.Connection, a_contains: str, b_contains: str) -> float:
    ra = con.execute(
        "SELECT course_id FROM courses WHERE title LIKE ? ORDER BY course_id LIMIT 1",
        (f"%{a_contains}%",)
    ).fetchone()
    rb = con.execute(
        "SELECT course_id FROM courses WHERE title LIKE ? ORDER BY course_id LIMIT 1",
        (f"%{b_contains}%",)
    ).fetchone()
    if not ra or not rb:
        return 0.0
    return compare_course_ids(con, ra[0], rb[0])

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/cursos.sqlite")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", nargs=2, type=int, metavar=("ID_A","ID_B"))
    g.add_argument("--urls", nargs=2, metavar=("URL_A","URL_B"))
    g.add_argument("--titles", nargs=2, metavar=("CONTAINS_A","CONTAINS_B"),
                   help="Compara el primer curso cuyo título contenga cada cadena")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        if args.ids:
            sim = compare_course_ids(con, args.ids[0], args.ids[1])
        elif args.urls:
            sim = compare_course_urls(con, args.urls[0], args.urls[1])
        else:
            sim = compare_course_titles_contains(con, args.titles[0], args.titles[1])
        print(f"Similaridad (coseno) = {sim:.4f}")
    finally:
        con.close()
