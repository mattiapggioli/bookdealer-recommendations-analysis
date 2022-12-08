from urllib.parse import urljoin
from os import path
import logging
import re
import csv
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.DEBUG)

DOMAIN = 'https://www.bookdealer.it/'


def main():
    path = '/i-consigli-dei-librai'
    # Compose URl
    book_rec_url = urljoin(DOMAIN, path)
    logging.info('Parsing %s', book_rec_url)
    book_rec_soup = get_soup(book_rec_url)
    last_page_button = book_rec_soup.find_all('a', {'class': 'next-btn'})[1]
    # Get last page number (after substring '?pag=')
    last_page = int(last_page_button['href'][5:])
    for page in range(1, last_page + 1):
        books_in_page = []
        logging.info('Parsing page %i', page)
        page_soup = get_soup(f'{book_rec_url}?pag={page}')
        book_headers = page_soup.find_all('div', {'class': 'product-header'})
        # Parse book data from every book in page
        for book_header in book_headers:
            book_path = book_header.select_one(r'a[href*=\/libro\/]')['href']
            book_url = urljoin(DOMAIN, book_path)
            book_data = parse_book_data(book_url)
            logging.info(book_data)
            books_in_page.append(book_data)
        logging.info('Page %i parsing completed', page)
        write_csv(data=books_in_page, filename='data/bd-recommendations.csv')
    logging.info('Parsing completed')


def get_soup(url):
    source = requests.get(url)
    soup = BeautifulSoup(source.text, 'html.parser')
    return soup


def parse_book_data(url_book):
    logging.info('Parsing book %s', url_book)
    book_data = {}
    book_soup = get_soup(url_book)
    book_info = book_soup.find('div', {'class': 'product-details-info'})
    # Title
    book_data['title'] = book_info.find('h3', {'class': 'product-title'}
                                        ).string
    # Price
    price_tag = book_info.find('span', {'class': 'price-new'}).string
    # Try formatting price in as int
    try:
        formatted_price = int(re.search(r'(\d+),\d\d €', price_tag).group(1))
        book_data['price'] = formatted_price
    except:
        logging.debug('Cannot convert price tag %s', price_tag)
        book_data['price'] = price_tag
    # Additional info
    # Get str format (easier to parse using re)
    add_info = book_info.find('ul', {'class': 'list-unstyled'}).text
    # Labels for matching with mapping
    add_info_mapping = {'Autore': 'author',
                        'Editore': 'publisher',
                        'Isbn': 'isbn',
                        'Categoria': 'category',
                        'Traduttore': 'translator',
                        'Numero pagine': 'pages',
                        'Data di Uscita': 'date',
                        'Collana': 'series'}
    for site_label in add_info_mapping:
        # Find info
        match = re.search(fr'{site_label}: (.+)\n', add_info)
        # Add information to dict with its respective key
        try:
            book_data[add_info_mapping[site_label]] = match.group(1)
        except AttributeError:
            logging.debug('Label %s missing', site_label.upper())
            book_data[add_info_mapping[site_label]] = None
    # List of indie bookstores that recommend the book
    try:
        bookstores = book_soup.find('div', {'class': 'w-consigliato-da'}
                                    ).select(r'a[href*=\/libreria\/]')
    except:
        bookstores = None
    if bookstores:
        # Number of recommendations
        book_data['recommendations'] = len(bookstores)
        # Get bookstore ids
        bookstores = [bookstore['href'][len('/libreria/'):]
                      for bookstore in bookstores]
        book_data['bookstores'] = ', '.join(bookstores)
    else:
        # Bookstores list may be missing
        # e.g. https://www.bookdealer.it/libro/9788804586890/la-breve-favolosa-vita-di-oscar-wao
        logging.debug('No bookstores found')
        book_data['recommendations'] = None
        book_data['bookstores'] = None
    # Book synopsis
    try:
        book_data['synopsis'] = book_soup.find('article', {'class': 'review-article'}).text
    except AttributeError:
        logging.debug('No synopsis found')
        book_data['synopsis'] = None
    return book_data


def write_csv(data, filename):
    # Check if file already exists to write column names only once
    if path.exists(filename):
        write_column_names = False
        logging.info('Creating CSV file')
    else:
        write_column_names = True
    # Write or keep writing CSV file
    with open(filename, 'a+', newline='', encoding='UTF-8') as output_file:
        dict_writer = csv.DictWriter(output_file, data[0].keys())
        if write_column_names:
            logging.info('Writing column names')
            dict_writer.writeheader()
        logging.info('Adding books')
        dict_writer.writerows(data)


if __name__ == '__main__':
    main()
