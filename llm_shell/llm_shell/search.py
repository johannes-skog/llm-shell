import aiohttp
import asyncio
from bs4 import BeautifulSoup


class URLFetcher:
    """
    A class for fetching content from URLs.
    """

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def fetch_page(self, url, method="GET", data=None, headers=None):
        if method.upper() == "POST":
            async with self.session.post(url, data=data, headers=headers) as response:
                return await response.text()
        else:
            async with self.session.get(url) as response:
                return await response.text()

    async def parse_page_content(self, url):

        html = ""
        try:
            html = await self.fetch_page(url)
        except UnicodeDecodeError as e:
            # Handle the error: log it, use a fallback encoding, etc.
            pass

        soup = BeautifulSoup(html, "html.parser")
        title = (
            soup.find("title").get_text(strip=True)
            if soup.find("title")
            else "No title found"
        )
        content_text = soup.get_text(separator=" ", strip=True)
        code_snippets = soup.find_all(["code", "pre"])
        codes = "\n\n\n".join([code.get_text(strip=True) for code in code_snippets])
        return {"title": title, "url": url, "content": content_text, "codes": codes}


async def url_fetch(url):
    async with aiohttp.ClientSession() as session:
        fetcher = URLFetcher(session)
        results = await fetcher.parse_page_content.get_results(url)
        return results


async def urls_fetch(urls):
    async with aiohttp.ClientSession() as session:
        fetcher = URLFetcher(session)
        tasks = [fetcher.parse_page_content(link) for link in urls]
        url_content = await asyncio.gather(*tasks)
        return url_content


class Search:
    """
    A class for searching the web and parsing search results.
    """

    def __init__(
        self, query, time_range: str = "", region: str = "", fetcher: URLFetcher = None
    ):
        self.query = query
        self.time_range = time_range
        self.region = region
        self.fetcher = fetcher

    async def parse_html_for_links(self, html):
        soup = BeautifulSoup(html, "html.parser")
        result_links = soup.find_all("a", class_="result__a")
        return [link["href"] for link in result_links]

    async def get_results(self, links_only: bool = False):
        # Fetch the initial search results page
        base_url = "https://html.duckduckgo.com/html/"
        data = {"q": self.query, "df": self.time_range, "kl": self.region}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        html = await self.fetcher.fetch_page(
            base_url, method="POST", data=data, headers=headers
        )

        # Parse the search results page for links
        links = await self.parse_html_for_links(html)

        if links_only:
            return links

        # Fetch and parse each page linked in the search results
        tasks = [self.fetcher.parse_page_content(link) for link in links]
        return await asyncio.gather(*tasks)


async def run_search(query, time_range="", region=""):
    async with aiohttp.ClientSession() as session:
        fetcher = URLFetcher(session)
        search = Search(query, time_range, region, fetcher)
        results = await search.get_results()
        return results


async def run_search_links(query, time_range="", region=""):
    async with aiohttp.ClientSession() as session:
        fetcher = URLFetcher(session)
        search = Search(query, time_range, region, fetcher)
        links = await search.get_results(links_only=True)
        return links
