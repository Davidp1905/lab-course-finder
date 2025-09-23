from __future__ import annotations

import bs4

import util
import crawler


def main() -> None:
    url = crawler.START_URL
    resp = util.get_request(url)
    if resp is None:
        print("Failed to GET start URL")
        return
    final_url = util.get_request_url(resp)
    text = util.read_request(resp)
    soup = bs4.BeautifulSoup(text, "html5lib")
    title = soup.title.text.strip() if soup.title else "<no title>"
    print(f"Fetched: {final_url}")
    print(f"Title: {title}")

    # Show first 10 links that pass filter
    links = list(crawler._extract_links(final_url, text))[:10]
    print("Sample links:")
    for link in links:
        print(f" - {link}")


if __name__ == "__main__":
    main()


