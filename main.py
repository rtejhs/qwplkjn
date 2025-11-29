import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import List

import pytz
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# GitHub token - will be automatically provided by GitHub Actions
git_access_token = os.environ.get("GITHUB_ACCESS_TOKEN")
if git_access_token is None:
    logging.warning("GITHUB_ACCESS_TOKEN not found in environment")


# Helper
class Article:
    def __init__(self, news_paper_name, publish_date, headline_1, headline_2, link, full_article):
        self.news_paper_name = news_paper_name
        self.publish_date = publish_date
        self.headline_1 = headline_1
        self.headline_2 = headline_2
        self.link = link
        self.full_article = full_article

    def to_dict(self):
        return {
            "news_paper_name": self.news_paper_name,
            "publish_date": self.publish_date,
            "headline_1": self.headline_1,
            "headline_2": self.headline_2,
            "link": self.link,
            "full_article": self.full_article
        }


def get_soup(url):
    try:
        html = requests.get(url, timeout=30)
        soup = BeautifulSoup(html.text, 'lxml')
    except requests.exceptions.RequestException as exception:
        logging.error(exception)
        return None
    return soup


def save_to_files(data: List[Article]):
    """Save scraped data to JSON files in the repository"""
    if not data or len(data) == 0:
        logging.warning("No data to save")
        return False
    
    # Create directory if it doesn't exist
    data_dir = "EdData/data/article"
    os.makedirs(data_dir, exist_ok=True)
    
    date = datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%d-%m-%Y')
    json_content = json.dumps([ob.to_dict() for ob in data], sort_keys=True, indent=4)
    
    # Save to main article list
    main_path = os.path.join(data_dir, "article_list.json")
    try:
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(json_content)
        logging.info(f"Saved {len(data)} articles to {main_path}")
    except Exception as e:
        logging.error(f"Failed to save main article list: {e}")
        return False
    
    # Save to date-specific file
    date_path = os.path.join(data_dir, f"{date}.json")
    try:
        with open(date_path, 'w', encoding='utf-8') as f:
            f.write(json_content)
        logging.info(f"Saved {len(data)} articles to {date_path}")
    except Exception as e:
        logging.error(f"Failed to save date-specific file: {e}")
        return False
    
    # Log what was scraped
    newspapers = set([article.news_paper_name for article in data])
    logging.info(f"Sources: {', '.join(newspapers)}")
    
    return True


class NewsScraper:
    def __init__(self, url, func):
        self.url = url
        self.scraperFunc = func

    def scrap(self):
        return self.scraperFunc(self.url)


# Daily Star Opinion url scrap
def daily_star_opinion_scraper(url):
    logging.info(f"Scraping {url}/opinion")
    soup = get_soup(f"{url}/opinion")
    if soup is None:
        return None

    cards = soup.find_all('div', {'class': 'card-content'}, limit=4)
    data = []
    for card in cards:
        link_parent = card.find('h3', {'class': 'title'})

        if link_parent is not None:
            link = link_parent.find('a')
            title = link_parent.text

            if link is not None:
                news_link = link.get('href', None)

                if news_link is not None:
                    full_url = f'https://www.thedailystar.net{news_link}'
                    logging.info(f"Scraping {full_url}")
                    article = scrap_daily_star_data(full_url)
                    if article is not None:
                        data.append(article)
                    else:
                        logging.warning(f"Scrap failed url: {full_url}")
    if len(data) > 0:
        return data
    return None


# Daily Star Editorial url scrap
def daily_star_editorial_scraper(url):
    logging.info("Scraping https://www.thedailystar.net/opinion/editorial")
    soup = get_soup('https://www.thedailystar.net/opinion/editorial')
    if soup is None:
        return None

    cards = soup.find_all('div', {'class': 'card-content card-content'}, limit=4)
    data = []
    for card in cards:
        link_parent = card.find('h4', {'class': 'title fs-18'})

        if link_parent is not None:
            link = link_parent.find('a')
            title = link_parent.text

            if link is not None:
                news_link = link.get('href', None)

                if news_link is not None:
                    full_url = f'https://www.thedailystar.net{news_link}'
                    logging.info(f"Scraping {full_url}")
                    article = scrap_daily_star_data(full_url)
                    if article is not None:
                        data.append(article)
                    else:
                        logging.warning(f"Scrap failed url: {full_url}")
    if len(data) > 0:
        return data
    return None


# The Hindu Editorial url scrap
def the_hindu_editorial_scraper(url):
    logging.info(f"Scraping {url}/editorial/")

    soup = get_soup(f"{url}/editorial/")
    if soup is None:
        return None
    articleUrlLinks1 = soup.find('div', {"class": "element wide-row-element"})
    news_links1 = articleUrlLinks1.find_all('a', limit=1)
    articleUrlLinks2 = soup.find('div', {"class": "element wide-row-element no-border"})
    news_links2 = articleUrlLinks2.find_all('a', limit=1)
    news_links = news_links1 + news_links2
    if news_links is None or len(news_links) == 0:
        return None

    data = []
    for link in news_links:
        news_link = link.get('href', None)

        if news_link is not None:
            logging.info(f"Scraping {news_link}")
            article = scrap_the_hindu_data(news_link)
            if article is not None:
                data.append(article)
            else:
                logging.warning(f"Scrap failed url: {news_link}")

    if len(data) > 0:
        return data
    return None


# The Hindu Editorial data scrap
def scrap_the_hindu_data(url):
    soup = get_soup(url)
    if soup is None:
        return None

    article = soup.find('div', {'class': 'col-xl-9 col-lg-8 col-md-12 col-sm-12 col-12 editorial'})
    if article is None:
        return None

    headline_element = article.find('h1', {'class': 'title'})
    if headline_element is None:
        return None

    headline = headline_element.text
    content = ""

    if headline is None or len(headline) == 0:
        return None

    headline = headline.strip()

    # sub title means subhead line
    headline_element2 = article.find('h2', {'class': 'sub-title'})
    if headline_element2 is None:
        return None

    headline2 = headline_element2.text
    content = ""

    if headline2 is None or len(headline2) == 0:
        return None

    headline2 = headline2.strip()

    content_elemnt = article.find('div', {'class': 'articlebodycontent col-xl-9 col-lg-12 col-md-12 col-sm-12 col-12'})
    if content_elemnt is None:
        return None

    content = content_elemnt.text

    if content != "":
        content = content.strip()

    if len(content) == 0:
        return None
    articleMainContent = content.split("To read this editorial")
    content = articleMainContent[0]

    return Article(
        news_paper_name="The Hindu",
        publish_date=datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%d-%m-%Y'),
        headline_1=headline,
        headline_2=headline2,
        link=url,
        full_article=content
    )


# The daily star article data scrap
def scrap_daily_star_data(url):
    soup = get_soup(url)
    if soup is None:
        return None

    reg = re.search(r'-\d+$', url)
    article_id = ""
    if reg:
        article_id = f'node{reg.group(0)}'

    if len(article_id) == 0:
        return None

    article = soup.find('article', {'id': article_id})
    if article is None:
        return None
    headline_element = soup.find('h1', {'class': 'fw-700 e-mb-16 article-title'})

    if headline_element is None:
        return None

    headline = headline_element.text
    content = ""

    content_elements = article.find_all('p')
    for paragraph in content_elements:
        content += paragraph.text
        content += "\n"

    if len(content) == 0:
        return None

    return Article(
        news_paper_name="The Daily Star",
        publish_date=datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%d-%m-%Y'),
        headline_1=headline,
        headline_2="",
        link=url,
        full_article=content
    )


# The Times of India Editorial url scrap
def the_time_Of_India_editorial_scraper(url):
    logging.info(f"Scraping {url}/blogs")
    soup = get_soup(f"{url}/blogs")
    if soup is None:
        return None

    cards = soup.find_all('div', {'class': 'blog-card'}, limit=4)
    data = []
    for card in cards:
        link_parent = card.find('div', {'class': 'title-date-wrap'})

        if link_parent is not None:
            link = link_parent.find('a')

            if link is not None:
                news_link = link.get('href', None)

                if news_link is not None:
                    logging.info(f"Scraping {news_link}")
                    article = scrap_the_times_of_india_data(news_link)
                    if article is not None:
                        data.append(article)
                    else:
                        logging.warning(f"Scrap failed url: {news_link}")
    if len(data) > 0:
        return data
    return None


# The Times of India article data scrap
def scrap_the_times_of_india_data(url):
    soup = get_soup(url)
    if soup is None:
        return None

    articleHeader = soup.find('div', {'class': 'show-header'})
    if articleHeader is None:
        return None

    headline_element = articleHeader.find('h1')
    if headline_element is None:
        return None

    headline = headline_element.text
    content = ""

    if headline is None or len(headline) == 0:
        return None

    headline = headline.strip()

    content_elemnt = soup.find('div', {'class': 'main-content single-article-content'})
    if content_elemnt is None:
        return None

    content = content_elemnt.text

    if content != "":
        content = content.strip()

    if len(content) == 0:
        return None
    articleMainContent = content.split("\nFacebook")
    content = articleMainContent[0]

    return Article(
        news_paper_name="The Times of India",
        publish_date=datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%d-%m-%Y'),
        headline_1=headline,
        headline_2="",
        link=url,
        full_article=content
    )


# The Financial Express Bd Editorial url scrap
def the_financial_express_editorial_scraper(url):
    logging.info(f"Scraping {url}")

    soup = get_soup(url)
    if soup is None:
        return None

    articleUrlLinks = soup.find('div', {"class": "col-lg-7 left-bar"})
    news_links = articleUrlLinks.find_all('a', {"class": "btn readmore btn-sm"}, limit=4)
    if news_links is None or len(news_links) == 0:
        return None

    data = []
    for link in news_links:
        news_link = link.get('href', None)

        if news_link is not None:
            logging.info(f"Scraping the url list {news_link}")
            article = scrap_the_financial_express_data(news_link)
            if article is not None:
                data.append(article)
            else:
                logging.warning(f"Scrap failed url: {news_link}")

    if len(data) > 0:
        return data
    return None


# The Financial Express Bd article data scrap
def scrap_the_financial_express_data(url):
    soup = get_soup(url)
    if soup is None:
        return None

    headline_element = soup.find('h1', {'class': 'single-heading'})
    if headline_element is None:
        return None

    headline = headline_element.text
    content = ""

    if headline is None or len(headline) == 0:
        return None

    headline = headline.strip()

    content_elemnt = soup.find('div', {"class": "col-lg-9 col-md-9 col-sm-12 col-xs-12 left-bar"})
    if content_elemnt is None:
        return None

    content_elements = content_elemnt.find_all('p')
    for paragraph in content_elements:
        content += paragraph.text
        content += "\n"
    if len(content) == 0:
        return None
    
    return Article(
        news_paper_name="The Financial Express",
        publish_date=datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%d-%m-%Y'),
        headline_1=headline,
        headline_2="",
        link=url,
        full_article=content
    )


def main():
    """Main function for GitHub Actions"""
    logging.info("=" * 60)
    logging.info("Starting news scraper...")
    logging.info("=" * 60)
    
    data = []
    
    try:
        theHinduEditorialScraper = NewsScraper("https://www.thehindu.com/opinion", the_hindu_editorial_scraper)
        theHinduEditorialData = theHinduEditorialScraper.scrap()
        if theHinduEditorialData is not None:
            data += theHinduEditorialData
    except Exception as e:
        logging.error(f"Scraping failed for The Hindu: {e}")

    try:
        theTimesOfIndiaEditorialScraper = NewsScraper("https://timesofindia.indiatimes.com",
                                                      the_time_Of_India_editorial_scraper)
        theTOIEditorialData = theTimesOfIndiaEditorialScraper.scrap()
        if theTOIEditorialData is not None:
            data += theTOIEditorialData
    except Exception as e:
        logging.error(f"Scraping failed for The Times of India: {e}")

    try:
        dailyStarOpinionScraper = NewsScraper("https://www.thedailystar.net/views", daily_star_opinion_scraper)
        dailyStarOpinionData = dailyStarOpinionScraper.scrap()
        if dailyStarOpinionData is not None:
            data += dailyStarOpinionData
    except Exception as e:
        logging.error(f"Scraping failed for The Daily Star Opinion BD: {e}")

    try:
        dailyStarEditorialScraper = NewsScraper("https://www.thedailystar.net/views", daily_star_editorial_scraper)
        dailyStarEditorialData = dailyStarEditorialScraper.scrap()
        if dailyStarEditorialData is not None:
            data += dailyStarEditorialData
    except Exception as e:
        logging.error(f"Scraping failed for The Daily Star Editorial BD: {e}")

    try:
        theFinancialExpressEditorialScraper = NewsScraper("https://today.thefinancialexpress.com.bd/editorial",
                                                          the_financial_express_editorial_scraper)
        theFinancialExpressEditorialData = theFinancialExpressEditorialScraper.scrap()
        if theFinancialExpressEditorialData is not None:
            data += theFinancialExpressEditorialData
    except Exception as e:
        logging.error(f"Scraping failed for The Financial express BD: {e}")

    logging.info("=" * 60)
    logging.info(f"Total articles scraped: {len(data)}")
    logging.info("=" * 60)
    
    # Save to files in the repository
    if save_to_files(data):
        logging.info("Successfully saved all files")
    else:
        logging.error("Failed to save files")
        sys.exit(1)
    
    logging.info("=" * 60)
    logging.info("Scraping completed!")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()