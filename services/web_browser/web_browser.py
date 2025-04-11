import asyncio
from typing import Any, List, Optional
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from app.app_types.gov_uk_search import DocumentBlacklistStatus, NonRagDocument
from app.config import BLACKLISTED_URLS, GOV_UK_BASE_URL, WEB_BROWSING_TIMEOUT, WHITELISTED_URLS

gov_uk_base_url_parsed = urlparse(GOV_UK_BASE_URL)

timeout = aiohttp.ClientTimeout(total=WEB_BROWSING_TIMEOUT)


class WebBrowserService:
    @staticmethod
    def strip_url(url: str) -> str:
        o = urlparse(url)
        if o.netloc == gov_uk_base_url_parsed.netloc or o.netloc == "":
            stripped_url = f"{GOV_UK_BASE_URL}{o.path}"
        else:
            # external links will be fetched using a simple https://host/path
            # pattern while #anchor or ?q=queries are stripped to prevent
            # likelihood of PII leaking (it is not 100% foolproof)
            stripped_url = f"{o.scheme}://{o.netloc}{o.path}"

        return stripped_url

    @staticmethod
    async def is_blacklisted(url: str) -> bool:
        # implement blacklisting here
        o = urlparse(url)
        # only allow URLs with www.gov.uk domain
        if o.netloc == "":
            return False
        if o.netloc != gov_uk_base_url_parsed.netloc:
            return True
        found_match = [matched_url for matched_url in BLACKLISTED_URLS if url.startswith(matched_url)]
        if len(found_match) > 0:
            return True
        return False

    @staticmethod
    async def is_whitelisted(url: str) -> bool:
        found_match = [matched_url for matched_url in WHITELISTED_URLS if url.startswith(matched_url)]
        if len(found_match) > 0:
            return True
        return False

    @staticmethod
    async def get_html_document(session: Any, url: str) -> NonRagDocument:
        stripped_url = WebBrowserService.strip_url(url)

        async with session.get(stripped_url, timeout=timeout) as response:
            doc_html = await response.text()
            soup = BeautifulSoup(doc_html, "html.parser")
            body = soup.find("body").text
            title = soup.find("title").text
            document = NonRagDocument(
                url=stripped_url,
                title=title.strip(),
                body=body.strip(),
                status=DocumentBlacklistStatus.OK,
            )
            return document

    @staticmethod
    async def make_blacklisted_document(url: str) -> NonRagDocument:
        return NonRagDocument(
            url=url,
            title="",
            body="",
            status=DocumentBlacklistStatus.BLACKLISTED,
        )

    @staticmethod
    async def get_documents(urls: List[str]) -> List[Optional[NonRagDocument]]:
        documents = []
        document_tasks = []

        async with aiohttp.ClientSession() as session:
            async with asyncio.TaskGroup() as tg:
                for url in urls:
                    whitelisted = await WebBrowserService.is_whitelisted(url)
                    blacklisted = await WebBrowserService.is_blacklisted(url)
                    if blacklisted:
                        document_tasks.append(tg.create_task(WebBrowserService.make_blacklisted_document(url=url)))
                    if whitelisted and not blacklisted:
                        document_tasks.append(
                            tg.create_task(WebBrowserService.get_html_document(session=session, url=url))
                        )
        for task in document_tasks:
            documents.append(task.result())

        return documents
