from bs4 import BeautifulSoup, SoupStrainer
import ssl
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.request import urlopen, Request
from retry import retry
import time
import re
import warnings
import Levenshtein as lev
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from typing import Union
from bs4.element import NavigableString
import logging
import os.path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from url_scraper.link_data import LinkData


__author__ = 'bmarx'

logger = logging.getLogger(__name__)


def make_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def make_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument('--headless')
    driver = webdriver.Chrome("C:/Users/14102/Brown/Realizing_Rights/drivers/chromedriver", options=options)
    driver.set_window_size(1600, 1600)
    return driver

@retry(tries=5)
def get_soup_from_html(qry: str, ct, prefix: str = 'https://search.brave.com/search?q=', timeout: float = 30):
    formatted_url = qry # prefix + urllib.parse.quote_plus(qry)
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    req = Request(url=formatted_url, headers=headers)
    response = urlopen(req)
    # soup = BeautifulSoup(response.text, 'html.parser')
    with urlopen(req, context=ct, timeout=timeout) as html:
        page = html.read()
        soup = BeautifulSoup(page, "html.parser")
        return soup


def find_in_url(url: str,
                item: int = -1,
                cleanup: bool = True) -> str:

    elements = re.findall(r"[^/]+", url)
    try:
        target = elements[item]
    except:
        msg = 'Index %d out of range. defaulting to last element in string.' % item
        warnings.warn(msg, UserWarning, stacklevel=2)
        target = elements[-1]
    
    if cleanup:
        target = re.sub(r'[^A-Za-z0-9]', " ", target)

    return target


def prepend_root_to_url(base_url: str, prefix: str) -> str:

    if base_url[0] == '/':
        url = prefix + base_url
    else:
        url = base_url

    url, _, _ = url.partition('?')
    url.removesuffix('/')
    return url


def is_local_link(url: str, root_url: str) -> bool:
    if url[0] == '/':
        return True
    if root_url in url:
        return True
    else:
        return False


def is_external_link(url: str) -> bool:
    if url.startswith('http'):
        return True
    else:
        return False


def try_getting_url_text(tag):
    text = tag.text

    if not text:
        text = tag.string
    if text:
        text = text.replace("\n", "")
        text = text.strip()

    return text



def format_dict_from_soup(tag: NavigableString, substring: str) -> dict:
    content = {}
    for span_vals in tag.find_all(class_=re.compile(substring)):
        # add qty to dictionary. key is nutrient name

        full_text = str(next(span_vals.stripped_strings))
        stripped_text = full_text.replace(' ', '')

        qty = re.findall(r'[0-9\.]+', stripped_text)
        qty_value = qty[0]
        try:
            unit = re.findall(r'[^0-9\.]+', stripped_text)
            unit_value = unit[0]
        except:
            unit_value = ''

        content[span_vals.get('class')[0]] = [qty_value, unit_value]

    return content


def closest_link_match(name, link_candidates) -> int:
    '''
    Calculate Levenshtein distance between one string and all strings in a list. Returns the string from the list
    that has the smallest edit distance. If the smallest distance is greater than the threshold, no string is returned.
    
    params: 
        name (String) : initial string
        link_candidates (List) : list of candidate strings
        
    returns: 
        the string with the smallest edit distance
    '''
    clst_url_score = 0
    for option in link_candidates:
        similarity = fuzz.partial_token_sort_ratio(name.lower(), option.lower())
        if similarity > clst_url_score:
            clst_url_score = similarity
    
    return clst_url_score


# TODO: Make this function able to write dictionaries of any form/nesting to csv
def write_to_csv(filename: str, data: dict, headers: Union[None, list]):

    with open(filename, 'w') as f:
        if headers is not None:
            column_names = ','.join(headers) + '\n'
            f.write(column_names)
        for i, r in data.items():
            for item in list(r):
                f.write("%s,%s\n" % (i, item)) 


def get_search_results(chunk) -> list:
    out_tuple_list = []
    for qry_rslt in chunk:
        url = qry_rslt.attrs['href']
        link_desc = qry_rslt.text
        if 'wikipedia' in url or '.com' in url or '.gov' in url:
            continue
        desc_cln = re.findall(r'[^\n]+', link_desc)[0]
        out_tuple_list.append((url, desc_cln))
    
    return out_tuple_list


def iterate_through_menus(drvr: webdriver.Chrome, actions: ActionChains):
    hover_menus = drvr.find_elements(By.CSS_SELECTOR, "[aria-haspopup='true'][aria-expanded='false']")
    menu_links = set()
    # Loop through each <select> element and move the mouse to it to expand its options
    for menu in hover_menus:
        # Wait for the menu to become visible
        
        hover = actions.move_to_element(menu)
        time.sleep(1)
        try:
            hover.perform()
        except:
            continue
        # Get the HTML for the expanded options and parse it with BeautifulSoup
        expanded_options_html = drvr.page_source
        expanded_options_soup = BeautifulSoup(expanded_options_html, "html.parser")

        # Find all <a> elements with an href attribute in the expanded options
        expanded_links = expanded_options_soup.find_all("a", href=True)

        # Add the expanded links to the links list
        menu_links.update(expanded_links)
    
    return menu_links


def recurse_scan_all_unique_links_in_site(url: str, base_url: str, drvr: webdriver.Chrome, actions: ActionChains, wait,
                                            link_keywords: list,
                                            local_link_set: set = set(),
                                            external_link_set: set = set(),
                                            depth: int = 0,
                                            blacklist_terms: list = []):

    if depth + 1 > 5:
        return local_link_set, external_link_set

    # First, try to get the web page.
    try:
        drvr.get(url)
    except:
        return set(), set()

    # Give the page time to load
    # Wait for the page to be fully loaded
    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

    # Dont bother with '404 error' pages
    if drvr.title.lower() == 'page not found':
        return set(), set()

    print(f'Depth {depth} for {url}')
    soup = BeautifulSoup(drvr.page_source, 'html.parser')
    # Find all Links on page
    raw_links = set(soup.find_all("a"))

    # Find links in drop down menus. Assuming the menus appear on every page so only get them the first time
    if depth == 0:
        menu_links = iterate_through_menus(drvr=drvr, actions=actions)
        raw_links.update(menu_links)

    # Compare new local links to old so we dont enter an infinite loop of links!
    new_local_link_set = set()
    for raw_link in raw_links:
        try:
            # Only pick up links with valid URL structure
            link_url = raw_link.attrs['href']
            link_url = prepend_root_to_url(link_url, base_url)
        except:
            continue

        link_text = try_getting_url_text(raw_link)
        if not link_text:
            continue
        
        if link_url == '':
            continue

        # Add link to proper set
        if is_local_link(link_url, base_url):
            if closest_link_match(name=link_text, link_candidates=link_keywords) > 80:
                new_local_link_set.add(LinkData(link_text, link_url, depth=depth))
        
        elif is_external_link(link_url):
            external_link_set.add(LinkData(link_text, link_url, depth=depth))
        
    # Only pick up links that did not appear in any other page seen so far
    new_links = new_local_link_set - local_link_set
    # Add those links to set of current links, but if they already exist do not overwrite previous instance
    local_link_set.update(new_local_link_set)
    # Sort links to iterate over by 'depth' (How many sections between slashes there are)
    new_links_sorted = sorted(list(new_links), key=lambda x: x.num_url_sections)
        
    for link in new_links_sorted:
        # Skip blacklisted terms 
        if any([term in link.link_url.lower() for term in blacklist_terms]):
            continue
        # Recursion time
        recursed_lcl_links, recursed_ext_links = recurse_scan_all_unique_links_in_site(url=link.link_url, 
                                                                                        base_url=base_url,
                                                                                        drvr=drvr, 
                                                                                        actions=actions,
                                                                                        wait=wait,
                                                                                        local_link_set=local_link_set,
                                                                                        external_link_set=external_link_set,
                                                                                        depth=depth + 1,
                                                                                        blacklist_terms=blacklist_terms,
                                                                                        link_keywords=link_keywords)
        local_link_set.update(recursed_lcl_links)
        external_link_set.update(recursed_ext_links)
    
    return local_link_set, external_link_set


if __name__ == '__main__':
    drvr = make_driver()

    actions = ActionChains(drvr)
    start_url = 'https://www.adirondackcsd.org'
    start_link_set = set()
    start_link_set.add(LinkData(link_text='adirondackcsd', link_url=start_url, depth=0))
    blacklist_terms = ['login', 'aspx', 'lightbox', 'file', '.php', '#', '.pdf', 'doc', 'jpg']
    wait = WebDriverWait(drvr, 5)
    link_keywords = ['boe meeting', 'board meeting', 'board of education', 'calendar',
                             'parent', 'meeting', 'video recording', 'board video recording', 'schedule']
    # Get ALL Internal and External links in a website
    recursed_lcl_links, recursed_ext_links = recurse_scan_all_unique_links_in_site(url=start_url,
                                                                                    base_url=start_url, 
                                                                                    local_link_set=start_link_set,
                                                                                    drvr=drvr, 
                                                                                    actions=actions,
                                                                                    blacklist_terms=blacklist_terms,
                                                                                    wait=wait,
                                                                                    link_keywords=link_keywords)

    # Identify External Links Pointing to social media sites 
    social_media_sites = ['youtube', 'vimeo', 'facebook', 'twitter']
    board_meeting_keywords = ['boe meeting', 'board meeting', 'boe recording', 'board recording',
                              'boe meeting recording', 'board meeting recording', 'boe meeting video',
                              'board meeting video', 'boe video recording', 'board video recording']

    boe_similarity_scores = {}
    for lcl_link in recursed_lcl_links:
        boe_similarity_scores[lcl_link.link_url] = closest_link_match(lcl_link.link_text, board_meeting_keywords)

    boe_similarity_scores = sorted(boe_similarity_scores.items(), key=lambda item: item[1], reverse=True)
    sites_identified = {}
    ext_link_list = list(recursed_ext_links)
    num_ext_links = len(ext_link_list)
    ext_id = 0
    while ext_id < num_ext_links:
        ext_link = ext_link_list[ext_id]
        scl_id = 0
        while scl_id < len(social_media_sites):
            if social_media_sites[scl_id] in ext_link.link_url:
                sites_identified[social_media_sites.pop(scl_id)] = ext_link.depth_found
            scl_id += 1

        ext_id += 1
        
        if len(social_media_sites) == 0:
            break

    print('done')
