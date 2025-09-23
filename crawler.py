import argparse
import time
import sqlite3
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


START_URL = "https://educacionvirtual.javeriana.edu.co/nuestros-programas-nuevo"
MAX_PAGES = 69


# -------------------------
# Utilidades de DB
# -------------------------
def init_db(db_path: str):
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def upsert_course(con, row):
    """
    row = dict(url, title, category, modality, duration, price, start_date, location,
               value_proposal, tutoria, description, raw_html, last_crawled_at)
    """
    insert_sql = """
    INSERT INTO courses (
      url, title, category, modality, duration, price, start_date, location,
      value_proposal, tutoria, description, raw_html, last_crawled_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(url) DO UPDATE SET
      title=excluded.title,
      category=excluded.category,
      modality=excluded.modality,
      duration=excluded.duration,
      price=excluded.price,
      start_date=excluded.start_date,
      location=excluded.location,
      value_proposal=excluded.value_proposal,
      tutoria=excluded.tutoria,
      description=excluded.description,
      raw_html=excluded.raw_html,
      last_crawled_at=excluded.last_crawled_at
    """
    con.execute(insert_sql, (
        row.get("url"),
        row.get("title"),
        row.get("category"),
        row.get("modality"),
        row.get("duration"),
        row.get("price"),
        row.get("start_date"),
        row.get("location"),
        row.get("value_proposal"),
        row.get("tutoria"),
        row.get("description"),
        row.get("raw_html"),
        row.get("last_crawled_at"),
    ))
    con.commit()


# -------------------------
# Selenium helpers
# -------------------------
def open_driver(headless=True):
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--lang=es-419")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.set_page_load_timeout(60)
    return driver


def _wait_results_loaded(wait: WebDriverWait):
    # Espera a que exista al menos un <li.item-programa>
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.item-programa.ais-Hits-item")))


def _first_card_title_text(driver) -> str:
    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")
    t = soup.select_one("li.item-programa .card-body b.card-title")
    return t.get_text(strip=True) if t else ""


# -------------------------
# Listado (catálogo)
# -------------------------
def get_cards_on_page(driver):
    """
    Devuelve los <li class="item-programa ..."> que renderiza el catálogo.
    """
    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")
    return soup.select("li.item-programa.ais-Hits-item")


def is_course_card(card_el):
    """
    En cada card hay un <div class="card-type course ...">Curso</div>.
    Queremos SOLO los que digan 'Curso'.
    """
    type_div = card_el.select_one("div.card-type")
    if not type_div:
        return False
    txt = type_div.get_text(strip=True).lower()
    return "curso" in txt


def extract_course_link_from_card(card_el, base_url: str):
    """
    El enlace a la ficha del curso está en el <a href="..."> del título (o de la imagen).
    Preferimos el <a> del título dentro de .card-body; si no, el primero que exista.
    """
    a = (card_el.select_one(".card-body a[href]") or
         card_el.select_one("a[href]"))
    if not a:
        return None
    href = a.get("href", "").strip()
    if not href:
        return None
    return urljoin(base_url, href)


def iterate_pages_and_collect_links(driver, start_url: str, pages: int, delay: float) -> set:
    wait = WebDriverWait(driver, 20)
    driver.get(start_url)
    _wait_results_loaded(wait)
    time.sleep(delay)

    links = set()
    last_first_title = _first_card_title_text(driver)

    for i in range(1, pages + 1):
        try:
            li = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"li#p{i}")))
            a = li.find_element(By.CSS_SELECTOR, "a.page-link")
            driver.execute_script("arguments[0].click();", a)

            # Espera a que el li tenga la clase de seleccionado
            wait.until(lambda d: "ais-Pagination-item--selected" in li.get_attribute("class"))

            # Espera a que cambie el primer título (para asegurar que no quedó la misma página)
            wait.until(lambda d: _first_card_title_text(d) != last_first_title)
            time.sleep(delay)
            last_first_title = _first_card_title_text(driver)

        except Exception:
            # Si i=1 ya está seleccionado, o si el sitio tardó: intentamos continuar
            pass

        cards = get_cards_on_page(driver)
        found_here = 0
        for card in cards:
            if not is_course_card(card):
                continue
            link = extract_course_link_from_card(card, start_url)
            if link:
                links.add(link)
                found_here += 1

        print(f"[p{i:02d}] cursos detectados aquí: {found_here} | acumulado: {len(links)}")
        time.sleep(0.2)

    return links


# -------------------------
# Ficha del curso
# -------------------------
def _text_or_none(el):
    return el.get_text(" ", strip=True) if el else None


def parse_course_detail(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    # Título: suele estar en h2.font-weight-bold.mb-md-0 (fallback a h1/h2)
    title_el = (soup.select_one("h2.font-weight-bold.mb-md-0") or
                soup.select_one("h1.font-weight-bold") or
                soup.select_one("h1, h2"))
    title = _text_or_none(title_el) or ""

    # Precio: <span class="course-price"><div>$ ...</div></span>
    price = _text_or_none(soup.select_one("span.course-price"))

    # Sidebar: NIVEL, DURACIÓN, TUTORÍA, INICIO (cada uno como h6 + valor en .col > div)
    def read_sidebar_value(label_text: str):
        h6 = soup.find("h6", class_="font-title-color m-0",
                       string=lambda s: s and label_text.lower() in s.lower())
        if not h6:
            return None
        row = h6.find_parent(class_="row")
        if not row:
            return None
        val = row.select_one(".col > div")
        return _text_or_none(val)

    category   = read_sidebar_value("NIVEL")        # solicitado como 'category'
    duration   = read_sidebar_value("DURACIÓN")
    tutoria    = read_sidebar_value("TUTORÍA")
    start_date = read_sidebar_value("INICIO")

    modality   = None     # no aparece en tu ejemplo
    location   = None     # no aparece en tu ejemplo

    # Propuesta de valor: bloque con clase específica
    vp_block = soup.select_one(".course-wrapper-seccion.course-wrapper-content--proposal")
    value_proposal = None
    if vp_block:
        header = vp_block.find(class_="font-weight-bold text-primary")
        if header:
            header.decompose()
        value_proposal = _text_or_none(vp_block)

    # Descripción (Presentación del programa)
    desc_block = soup.select_one(".course-wrapper-seccion.course-wrapper-content--presentation")
    description = None
    if desc_block:
        header = desc_block.find(class_="font-weight-bold text-primary")
        if header:
            header.decompose()
        description = _text_or_none(desc_block)

    return {
        "url": url,
        "title": title,
        "category": category,
        "modality": modality,
        "duration": duration,
        "price": price,
        "start_date": start_date,
        "location": location,
        "value_proposal": value_proposal,
        "tutoria": tutoria,
        "description": description,
    }


# -------------------------
# Flujo principal
# -------------------------
def crawl(args):
    con = init_db(args.db)
    driver = open_driver(headless=not args.show)

    try:
        # 1) recopilar enlaces de cursos en el catálogo (paginación p1..p{pages})
        course_links = iterate_pages_and_collect_links(driver, args.start, args.pages, args.delay)
        print(f"Total de enlaces de cursos: {len(course_links)}")

        # 2) visitar fichas y guardar
        visited = 0
        for link in sorted(course_links):
            try:
                driver.get(link)
                time.sleep(args.delay)  # breve espera por render
                detail_html = driver.page_source
                data = parse_course_detail(detail_html, link)
                data["raw_html"] = detail_html if args.save_html else None
                data["last_crawled_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

                if not data["title"]:
                    print(f"[SKIP] Sin título: {link}")
                    continue

                upsert_course(con, data)
                visited += 1
                if visited % 10 == 0:
                    print(f"Guardados: {visited}/{len(course_links)}")
                time.sleep(0.2)

            except Exception as e:
                print(f"[ERROR] {link}: {e}")

        print(f"Listo. Cursos guardados/actualizados: {visited}")

    finally:
        driver.quit()
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/cursos.sqlite")
    ap.add_argument("--start", default=START_URL)
    ap.add_argument("--pages", type=int, default=MAX_PAGES)
    ap.add_argument("--delay", type=float, default=1.0, help="Segundos entre acciones")
    ap.add_argument("--save-html", action="store_true", help="Guardar raw_html")
    ap.add_argument("--show", action="store_true", help="Mostrar navegador (quit headless)")
    args = ap.parse_args()
    crawl(args)


if __name__ == "__main__":
    main()
