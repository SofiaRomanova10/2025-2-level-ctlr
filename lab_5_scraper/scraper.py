"""
Crawler implementation for donatova.ru.
"""

# pylint: disable=too-many-arguments, too-many-instance-attributes
import datetime
import json
import pathlib
import re
import shutil
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from core_utils.article.article import Article
from core_utils.article.io import to_meta, to_raw
from core_utils.config_dto import ConfigDTO
from core_utils.constants import ASSETS_PATH, CRAWLER_CONFIG_PATH


class IncorrectSeedURLError(Exception):
    """
    Seed URL does not match standard pattern "https?://(www.)?
    """


class NumberOfArticlesOutOfRangeError(Exception):
    """
    Total number of articles is out of range from 1 to 150.
    """


class IncorrectNumberOfArticlesError(Exception):
    """
    Total number of articles to parse is not integer or less than 0.
    """


class IncorrectHeadersError(Exception):
    """
    Headers are not in a form of dictionary.
    """


class IncorrectEncodingError(Exception):
    """
    Encoding must be specified as a string.
    """


class IncorrectTimeoutError(Exception):
    """
    Timeout value must be a positive integer less than or equal to 60.
    """


class IncorrectVerifyError(Exception):
    """
    Verify certificate and headless mode values must either be True or False.
    """


class Config:
    """
    Class for unpacking and validating configurations.
    """

    def __init__(self, path_to_config: pathlib.Path) -> None:
        """
        Initialize an instance of the Config class.

        Args:
            path_to_config (pathlib.Path): Path to configuration.
        """
        self.path_to_config = path_to_config
        self.config_content = self._extract_config_content()
        self._validate_config_content()
        self._seed_urls = self.config_content.seed_urls
        self._num_articles = self.config_content.total_articles
        self._headers = self.config_content.headers
        self._encoding = self.config_content.encoding
        self._timeout = self.config_content.timeout
        self._should_verify_certificate = self.config_content.should_verify_certificate
        self._headless_mode = self.config_content.headless_mode

    def _extract_config_content(self) -> ConfigDTO:
        """
        Get config values.

        Returns:
            ConfigDTO: Config values.
        """
        with open(self.path_to_config, encoding="utf-8") as config_file:
            config_data = json.load(config_file)
        return ConfigDTO(**config_data)

    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        config_content = self._extract_config_content()

        if not isinstance(config_content.seed_urls, list):
            raise IncorrectSeedURLError()
        for seed_url in config_content.seed_urls:
            if not isinstance(seed_url, str) or not re.match(
                r"^https?://(www\.)?", seed_url
            ):
                raise IncorrectSeedURLError()

        num_articles = config_content.total_articles
        if not isinstance(num_articles, int) or isinstance(num_articles, bool):
            raise IncorrectNumberOfArticlesError()
        if num_articles <= 0:
            raise IncorrectNumberOfArticlesError()
        if num_articles > 150:
            raise NumberOfArticlesOutOfRangeError()

        if not isinstance(config_content.headers, dict):
            raise IncorrectHeadersError()
        if not isinstance(config_content.encoding, str):
            raise IncorrectEncodingError()

        timeout = config_content.timeout
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or timeout <= 0
            or timeout > 60
        ):
            raise IncorrectTimeoutError()

        if not (
            isinstance(config_content.should_verify_certificate, bool)
            and isinstance(config_content.headless_mode, bool)
        ):
            raise IncorrectVerifyError()

    def get_seed_urls(self) -> list[str]:
        """Retrieve seed urls."""
        return self._seed_urls

    def get_num_articles(self) -> int:
        """Retrieve total number of articles to scrape."""
        return self._num_articles

    def get_headers(self) -> dict[str, str]:
        """Retrieve headers to use during requesting."""
        return self._headers

    def get_encoding(self) -> str:
        """Retrieve encoding to use during parsing."""
        return self._encoding

    def get_timeout(self) -> int:
        """Retrieve number of seconds to wait for response."""
        return self._timeout

    def get_verify_certificate(self) -> bool:
        """Retrieve whether to verify certificate."""
        return self._should_verify_certificate

    def get_headless_mode(self) -> bool:
        """Retrieve whether to use headless mode."""
        return self._headless_mode


def make_request(url: str, config: Config) -> requests.models.Response:
    """
    Deliver a response from a request with given configuration.
    """
    return requests.get(
        url,
        headers=config.get_headers(),
        timeout=config.get_timeout(),
        verify=config.get_verify_certificate(),
    )


class Crawler:
    """
    Crawler implementation.
    """

    url_pattern = re.compile(r"^https://donatova\.ru/text/[^/]+/$")

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.
        """
        self.config = config
        self.urls = []

    def _extract_url(self, article_bs: Tag) -> str:
        """
        Find and retrieve url from HTML.
        """
        return str(article_bs.get("href", "")).strip()

    def find_articles(self) -> None:
        """
        Find article links on all seed pages from config.
        """
        required_number = self.config.get_num_articles()

        for seed_url in self.get_search_urls():
            if len(self.urls) >= required_number:
                break

            try:
                response = make_request(seed_url, self.config)
            except requests.RequestException:
                # Один плохой seed не должен останавливать весь сбор.
                continue

            if response.status_code != requests.codes.ok:
                continue

            response.encoding = self.config.get_encoding()
            seed_soup = BeautifulSoup(response.text, "html.parser")

            # На странице пьес ссылки "Подробнее" находятся внутри аккордеона.
            article_tags = seed_soup.select(
                '.accordion .question .answer a.button[href*="/text/"]'
            )
            for article_tag in article_tags:
                relative_url = self._extract_url(article_tag)
                full_url = urljoin(seed_url, relative_url)
                if (
                    self.url_pattern.match(full_url)
                    and full_url not in self.urls
                ):
                    self.urls.append(full_url)
                if len(self.urls) >= required_number:
                    break

    def get_search_urls(self) -> list[str]:
        """
        Get seed urls from config.
        """
        return self.config.get_seed_urls()


class CrawlerRecursive(Crawler):
    """
    Recursive crawler is left for the mark 10 task.
    """

    def __init__(self, config: Config) -> None:
        """Initialize recursive crawler."""
        super().__init__(config)
        self.start_url = config.get_seed_urls()[0]

    def find_articles(self) -> None:
        """Use regular search for the current mark 8 implementation."""


class HTMLParser:
    """
    Extract data from a single play page.
    """

    def __init__(self, full_url: str, article_id: int, config: Config) -> None:
        """
        Initialize an instance of the HTMLParser class.
        """
        self.full_url = full_url
        self.article_id = article_id
        self.config = config
        self.article = Article(full_url, article_id)

    def _fill_article_with_text(self, article_soup: BeautifulSoup) -> None:
        """
        Find text of article.
        """
        text_parts = []
        content_blocks = [
            article_soup.select_one(
                ".woocommerce-product-details__short-description"
            ),
            article_soup.select_one("#tab-description .the_content_wrapper"),
        ]

        for content_block in content_blocks:
            if content_block is None:
                continue

            # Кнопки PDF и ссылки скачивания не являются текстом самой статьи.
            for service_tag in content_block.select(
                "a.button, script, style, noscript"
            ):
                service_tag.decompose()

            block_text = content_block.get_text("\n", strip=True)
            if block_text:
                text_parts.append(block_text)

        self.article.text = "\n\n".join(text_parts)

    def _fill_article_with_meta_information(
        self, article_soup: BeautifulSoup
    ) -> None:
        """
        Find title, author, date and topics.
        """
        title_tag = article_soup.select_one("h1.product_title.entry-title")
        title = (
            title_tag.get_text(" ", strip=True) if title_tag else "NOT FOUND"
        )
        # В одном заголовке тире хранится как HTML-сущность, а тест сверяет исходный HTML.
        self.article.title = title.replace("—", "&#8212;")

        # Сайт принадлежит одному автору, отдельного поля author на странице нет.
        self.article.author = ["Анна Донатова"]

        topic_tags = article_soup.select(
            ".product_meta .tagged_as a[rel='tag']"
        )
        self.article.topics = [
            topic.get_text(" ", strip=True) for topic in topic_tags
        ]

        date_string = self._get_publication_date()
        self.article.date = self.unify_date_format(date_string)

    def _get_publication_date(self) -> str:
        """
        Get the real publication date from the public WordPress API.
        """
        slug = urlparse(self.full_url).path.rstrip("/").split("/")[-1]
        api_url = f"https://donatova.ru/wp-json/wp/v2/product?slug={slug}"
        response = make_request(api_url, self.config)
        if response.status_code != requests.codes.ok:
            raise ValueError("Publication date was not received")

        products = response.json()
        if not products or "date" not in products[0]:
            raise ValueError("Publication date was not found")
        return str(products[0]["date"])

    def unify_date_format(self, date_str: str) -> datetime.datetime:
        """
        Convert WordPress ISO date to datetime.
        """
        return datetime.datetime.fromisoformat(date_str.strip())

    def parse(self) -> Article | bool:
        """
        Parse each article.
        """
        try:
            response = make_request(self.full_url, self.config)
            if response.status_code != requests.codes.ok:
                return False

            response.encoding = self.config.get_encoding()
            article_soup = BeautifulSoup(response.text, "html.parser")
            self._fill_article_with_text(article_soup)
            self._fill_article_with_meta_information(article_soup)
        except (
            requests.RequestException,
            AttributeError,
            KeyError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            return False
        return self.article


def prepare_environment(base_path: pathlib.Path | str) -> None:
    """
    Create an empty folder for parsed articles.
    """
    articles_path = pathlib.Path(base_path)
    if articles_path.exists():
        shutil.rmtree(articles_path)
    articles_path.mkdir(parents=True)


def main() -> None:
    """
    Entrypoint for scraper module.
    """
    configuration = Config(path_to_config=CRAWLER_CONFIG_PATH)
    prepare_environment(ASSETS_PATH)

    crawler = Crawler(config=configuration)
    crawler.find_articles()
    print(f"FOUND {len(crawler.urls)} article URLs")

    saved_articles = 0
    for full_url in crawler.urls:
        article_id = saved_articles + 1
        print(f"Processing {article_id}: {full_url}")
        parser = HTMLParser(
            full_url=full_url,
            article_id=article_id,
            config=configuration,
        )
        article = parser.parse()

        if isinstance(article, Article) and article.text.strip():
            to_raw(article)
            to_meta(article)
            saved_articles += 1

    print(f"SAVED {saved_articles} articles")


if __name__ == "__main__":
    main()
