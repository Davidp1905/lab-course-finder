from __future__ import annotations

from typing import List, Optional
import logging
import re
import urllib.parse as urlparse

import bs4
from bs4.element import Tag
import requests


# Configure a basic logger for warnings/info during crawling
logging.basicConfig(level=logging.INFO)


_SESSION: Optional[requests.Session] = None
_DEFAULT_TIMEOUT_SECONDS: int = 15
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )
}


def _get_session() -> requests.Session:
    """Return a shared requests.Session, creating it if needed."""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(_DEFAULT_HEADERS)
    return _SESSION


def is_absolute_url(url: str) -> bool:
    """Return True if the URL is absolute (http or https)."""
    if not url:
        return False
    parsed = urlparse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def convert_if_relative_url(page_url: str, discovered_url: str) -> Optional[str]:
    """Return absolute URL for discovered_url relative to page_url.

    - If discovered_url is already absolute (http/https), return it.
    - If it is relative, join with page_url and return the absolute equivalent.
    - Return None if conversion fails or the result is not http/https.
    """
    if not discovered_url:
        return None

    discovered_url = discovered_url.strip()
    # Discard javascript/tel/mail links up-front
    if discovered_url.startswith(("javascript:", "tel:", "mailto:")):
        return None

    try:
        if is_absolute_url(discovered_url):
            abs_url = discovered_url
        else:
            abs_url = urlparse.urljoin(page_url, discovered_url)
        parsed = urlparse.urlparse(abs_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return abs_url
    except Exception:
        return None
    return None


def remove_fragment(url: str) -> str:
    """Remove the fragment part (#...) from the URL."""
    if not url:
        return url
    defragmented, _frag = urlparse.urldefrag(url)
    return defragmented


def get_request(url: str) -> Optional[requests.Response]:
    """Perform an HTTP GET request and return a Response, or None on failure."""
    if not is_absolute_url(url):
        return None
    try:
        session = _get_session()
        response = session.get(url, timeout=_DEFAULT_TIMEOUT_SECONDS, allow_redirects=True)
        # Consider only successful responses as usable
        if response.status_code >= 200 and response.status_code < 400:
            return response
        logging.warning("HTTP %s for URL: %s", response.status_code, url)
        return None
    except requests.RequestException as exc:
        logging.warning("Request failed for URL %s: %s", url, exc)
        return None


def read_request(response: requests.Response) -> str:
    """Return the text content of a Response as a string.

    This function decodes bytes using UTF-8 with replacement to avoid decode errors.
    Logs a warning if undecodable characters were replaced.
    """
    if response is None:
        return ""
    try:
        # Use content to control decoding strictly
        text = response.content.decode("utf-8", errors="replace")
        if "\ufffd" in text:  # REPLACEMENT CHARACTER present
            logging.warning(
                "Some characters could not be decoded for %s and were replaced",
                get_request_url(response),
            )
        return text
    except Exception as exc:
        logging.warning("Failed reading response for %s: %s", get_request_url(response), exc)
        return ""


def get_request_url(response: requests.Response) -> str:
    """Return the final URL associated with a Response (after redirects)."""
    if response is None:
        return ""
    return response.url or ""


_FILENAME_EXT_PATTERN = re.compile(r"\.([A-Za-z0-9]+)$")


def _filename_extension(path: str) -> str:
    """Return the lowercase extension of the last path segment, including dot, or ''."""
    if not path:
        return ""
    # Get the last non-empty segment
    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return ""
    last = segments[-1]
    match = _FILENAME_EXT_PATTERN.search(last)
    return f".{match.group(1).lower()}" if match else ""


def is_url_ok_to_follow(url: str, domain: str) -> bool:
    """Return True if the URL is absolute, in the specified domain, safe, and html-like.

    Conditions:
    1) Absolute URL (http/https)
    2) Falls within the given domain (exact match or subdomain)
    3) Does not contain '@' or 'mailto:'
    4) Filename ends with no extension, '.html', or is a directory path
    """
    if not is_absolute_url(url):
        return False

    if "@" in url or url.lower().startswith("mailto:"):
        return False

    parsed = urlparse.urlparse(url)
    netloc = (parsed.netloc or "").lower()
    domain = (domain or "").lower()
    if not (netloc == domain or netloc.endswith("." + domain)):
        return False

    path = parsed.path or "/"
    ext = _filename_extension(path)
    # Accept directories (no file name), pages without extension, or .html
    if path.endswith("/"):
        return True
    if ext == "":
        return True
    if ext == ".html":
        return True
    return False


def find_sequence(tag: Tag) -> List[Tag]:
    """Given a bs4 Tag, return a list of 'div.card-body' tags for its subsequence.

    If the tag corresponds to a sequence container (per lab: class contains
    'item-programa' and related classes), we return the nested course blocks
    with class 'card-body'. Otherwise, return an empty list.
    """
    if tag is None or not isinstance(tag, Tag):
        return []

    classes = set(tag.get("class", []))
    if not classes:
        return []

    # Heuristic: presence of 'item-programa' indicates a sequence container.
    if "item-programa" in classes:
        return list(tag.find_all("div", class_="card-body"))

    return []


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication: strip fragment, lowercase scheme/host.

    Keeps path/query as-is (except fragment removal) to avoid over-collapsing distinct pages.
    """
    if not url:
        return ""
    url = remove_fragment(url)
    parsed = urlparse.urlparse(url)
    normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    return urlparse.urlunparse(normalized)
