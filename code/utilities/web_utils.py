from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.request import urlopen, Request
import time
import re
import warnings
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import logging
import os.path
import sys

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
gparentdir = os.path.dirname(parentdir)
sys.path.append(parentdir)
sys.path.append(gparentdir)

from url_scraper.link_data import LinkData
from objects.scrape_lists import blacklist_terms, link_keywords, board_meeting_keywords, social_media_sites

__author__ = 'bmarx'

logger = logging.getLogger(__name__)


def make_https(url) -> str:
    try:
        strt, prt, url = url.partition('://')
        if url[-1] == '/':
            url = url[:-1]
    except:
        return None

    new_url = 'https' + prt + url

    return new_url


def make_driver_utils():
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    # options.add_argument('--headless')
    options.add_argument("--disable-features=AutoplayIgnoreWebAudio")
    driver = webdriver.Chrome("drivers/chromedriver.exe", options=options)
    driver.set_window_size(1600, 1600)
    actions = ActionChains(driver)
    wait = WebDriverWait(driver, 5)

    return driver, actions, wait


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


def prepend_root_to_url(base_url: str, prefix: str, subdomain: str = 'www') -> str:
    # If URL only provides path to page without Root URL, add the root
    if base_url[0] == '/':
        url = prefix + base_url
    else:
        url = base_url

    # Some URLs have a custom subdomain instead of 'www.' In these cases, dont add the 'www' to the start
    url = make_https(url.removesuffix('/'))
    if not url:
        url = prefix + '/' + base_url
    elif not url.startswith(f'https://{subdomain}.') and len(get_url_components(url=url)) < 3:
        url = f'https://{subdomain}.' + url.removeprefix('https://')
    

    return url


def is_local_link(url: str, root_url: str) -> bool:
    if root_url in url:
        return True
    else:
        return False


def is_external_link(url: str, root_url: str) -> bool:
    
    if url.startswith(root_url):
        return False
    if url.startswith('http'):
        return True
    else:
        return False


def try_getting_url_text(tag):
    text = tag.text

    if not text:
        text = tag.string
    if text:
        text = text.strip('\n\t ')
        text = text.partition('\n')[0]
        # Ignore link names that are too long
        if len(text) > 50:
            text = None
        elif len(text) < 3:
            text = None

    return text


def get_subdomain(url: str) -> str:
    url_components = get_url_components(url=url)
    if len(url_components) >= 3: 
        sdomain = url_components[0]
    else:
        sdomain = 'www'
    
    return sdomain


def get_url_components(url: str) -> list:
    url_root = find_in_url(url=url, item=1, cleanup=False)
    url_comps = url_root.partition('.')

    return url_comps


def closest_link_match(name, link_candidates) -> int:
    '''
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


def iterate_through_menus(drvr: webdriver.Chrome, actions: ActionChains):
    # hover_menus = drvr.find_elements(By.CSS_SELECTOR, "[aria-haspopup='true'][aria-expanded='false']")
    # if not hover_menus:
    hover_menus = drvr.find_elements(By.CSS_SELECTOR, "[aria-expanded='false']")
    menu_links = set()
    orig_url = drvr.current_url
    # Loop through each <select> element and move the mouse to it to expand its options
    for menu in hover_menus:
        # Wait for the menu to become visible
        
        hover = actions.move_to_element(menu)
        try:
            
            hover.click(on_element=menu)
            hover.perform()
            # actions.click()
            time.sleep(1)
        except:
            continue
        # Get the HTML for the expanded options and parse it with BeautifulSoup
        expanded_options_html = drvr.page_source
        expanded_options_soup = BeautifulSoup(expanded_options_html, "html.parser")

        # Find all <a> elements with an href attribute in the expanded options
        expanded_links = expanded_options_soup.find_all("a", href=True)

        # Add the expanded links to the links list
        menu_links.update(set(expanded_links))

        actions.send_keys(Keys.ESCAPE).perform()
    
    return menu_links


def recurse_scan_all_unique_links_in_site(url: str, base_url: str, drvr: webdriver.Chrome, actions: ActionChains, wait,
                                            link_keywords: list,
                                            local_link_set: set = set(),
                                            external_link_set: set = set(),
                                            depth: int = 0,
                                            blacklist_terms: list = [],
                                            subdomain: str = 'www'):

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

    if depth == 0:
        # Accounting for redirects to other url names
        subdomain = get_subdomain(url=drvr.current_url)
        base_url = prepend_root_to_url(base_url=drvr.current_url, prefix='', subdomain=subdomain)
        base_url = find_in_url(url=base_url, item=0, cleanup=False) + '//' + find_in_url(url=base_url, item=1, cleanup=False) 
        url = base_url
        # Find links in drop down menus. Assuming the menus appear on every page so only get them the first time
        menu_links = iterate_through_menus(drvr=drvr, actions=actions)
        raw_links.update(menu_links)

    # Compare new local links to old so we dont enter an infinite loop of links!
    new_local_link_set = set()
    for raw_link in raw_links:
        try:
            # Only pick up links with valid URL structure
            link_url = raw_link.attrs['href']
            # Skip blacklisted terms 
            if any([term in link_url.lower() for term in blacklist_terms]):
                continue
            link_url = prepend_root_to_url(link_url, base_url, subdomain=subdomain)
        except:
            continue

        link_text = try_getting_url_text(raw_link)

        if is_external_link(link_url, base_url):
            external_link_set.add(LinkData(link_text, link_url, depth=depth))

        # Add link to proper set
        elif is_local_link(link_url, base_url):
            if not link_text:
                continue
            if closest_link_match(name=link_text, link_candidates=link_keywords) > 90:
                new_local_link_set.add(LinkData(link_text, link_url, depth=depth))
        
    # Only pick up links that did not appear in any other page seen so far
    new_links = new_local_link_set - local_link_set
    # Add those links to set of current links, but if they already exist do not overwrite previous instance
    local_link_set.update(new_local_link_set)
    # Sort links to iterate over by 'depth' (How many sections between slashes there are)
    new_links_sorted = sorted(list(new_links), key=lambda x: x.num_url_sections)
        
    for link in new_links_sorted:
        print(' '*(depth+1) + '|_' + str(depth) + ': ' + str(len(local_link_set)))
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
                                                                                        link_keywords=link_keywords,
                                                                                        subdomain=subdomain)
        local_link_set.update(recursed_lcl_links)
        external_link_set.update(recursed_ext_links)

    return local_link_set, external_link_set


if __name__ == '__main__':
    drvr, actions, wait = make_driver_utils()

    start_url = 'https://www.srvusd.net'
    start_link_set = set()
    start_link_set.add(LinkData(link_text='BASE', link_url=start_url, depth=0))

    # Get ALL Internal and External links in a website
    recursed_lcl_links, recursed_ext_links = recurse_scan_all_unique_links_in_site(url=start_url,
                                                                                    base_url=start_url, 
                                                                                    local_link_set=start_link_set,
                                                                                    drvr=drvr, 
                                                                                    actions=actions,
                                                                                    blacklist_terms=blacklist_terms,
                                                                                    wait=wait,
                                                                                    link_keywords=link_keywords)

    boe_similarity_scores = {}
    cur_sim = 60
    best_link = None
    all_links = recursed_lcl_links
    all_links.update(recursed_ext_links)
    all_links_sorted = sorted(list(all_links), key=lambda x: x.depth_found)
    ext_links_sorted = sorted(list(recursed_ext_links), key=lambda x: x.depth_found)

    for link in all_links_sorted:
        if cur_sim == 100:
            break
        if not link.link_text:
            continue

        sim = closest_link_match(link.link_text, board_meeting_keywords)
        if sim > cur_sim:
            best_link = link
            cur_sim = sim

    # Identify External Links Pointing to social media sites 
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
