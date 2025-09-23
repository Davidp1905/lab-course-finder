import argparse
import sqlite3

def get_synonyms(con, term: str) -> set:
    synonyms = set()
    t = term.strip().lower()
    row = con.execute("SELECT term_id FROM terms WHERE lower(term)=?", (t,)).fetchone()
    if not row:
        return synonyms
    term_id = row[0]
    for (syn,) in con.execute("SELECT synonym FROM synonyms WHERE term_id=?", (term_id,)):
        if syn:
            synonyms.add(syn.strip().lower())
    return synonyms

def build_fts_query(terms: list, con: sqlite3.Connection) -> str:
    """
    Crea el MATCH de FTS combinando término + sinónimos con OR.
    E.g.: (ia OR "inteligencia artificial") OR (python)
    """
    groups = []
    for t in terms:
        t = t.strip()
        if not t:
            continue
        syns = get_synonyms(con, t)
        parts = {t.lower()} | {s.lower() for s in syns}
        parts_q = [f'"{p}"' if " " in p else p for p in parts]
        groups.append("(" + " OR ".join(parts_q) + ")")
    return " OR ".join(groups) if groups else ""

def search(con, interests: list, top: int = 20):
    match = build_fts_query(interests, con)
    if not match:
        return []

    # Intentar ordenar por BM25 (si tu SQLite lo soporta).
    try:
        sql = """
        SELECT c.url, c.title, bm25(courses_fts) as score
        FROM courses_fts f
        JOIN courses c ON c.course_id = f.rowid
        WHERE courses_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """
        return list(con.execute(sql, (match, top)))
    except sqlite3.OperationalError:
        # Fallback sin bm25
        sql = """
        SELECT c.url, c.title, f.rowid as score
        FROM courses_fts f
        JOIN courses c ON c.course_id = f.rowid
        WHERE courses_fts MATCH ?
        LIMIT ?
        """
        return list(con.execute(sql, (match, top)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/cursos.sqlite")
    ap.add_argument("--intereses", required=True, help='Ej: "inteligencia artificial, python, datos"')
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    interests = [t.strip() for t in args.intereses.split(",")]
    con = sqlite3.connect(args.db)
    rows = search(con, interests, args.top)
    for url, title, score in rows:
        print(f"- {title}  (score={score})\n  {url}\n")
    con.close()

if __name__ == "__main__":
    main()
