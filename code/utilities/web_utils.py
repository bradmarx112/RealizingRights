from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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

from objects.scrape_lists import disability_keywords, disability_link_keywords
from url_scraper.link_data import LinkData


__author__ = 'bmarx'

logger = logging.getLogger('selenium')

MAX_THREAD_COUNT = 11


def make_https(url) -> str:
    '''
    Replaces URL protocol with HTTPS and returns completed string, or replaces string with None if malformed.
    '''
    try:
        strt, prt, url = url.partition('://')
        if url[-1] == '/':
            url = url[:-1]
    except:
        return None

    new_url = 'https' + prt + url

    return new_url


def make_driver_utils():
    '''
    Sets up Selenium objects for scraping:
    
    - Headless Google Chrome driver
    - ActionChain object
    - WebDriverWait object
    '''
    service = Service()
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.headless = True
    options.add_argument("--disable-features=AutoplayIgnoreWebAudio")
    options.add_argument('--mute-audio')
    options.page_load_strategy = 'eager'
    # Set user agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36")
    
    
    # Adding to fix Timed out receiving message from renderer errors
    # https://stackoverflow.com/questions/48450594/selenium-timed-out-receiving-message-from-renderer
    # options.add_experimental_option( "prefs",{'profile.managed_default_content_settings.javascript': 2})
    # options.add_argument("--disable-gpu")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    # options.add_argument("--disable-browser-side-navigation")
    # options.add_argument("--no-sandbox")
    # options.add_argument("--disable-dev-shm-usage")
    # driver = webdriver.Chrome("drivers/chromedriver.exe", options=options)
    # driver = webdriver.Chrome(service=service, options=options)
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    driver.set_window_size(1600, 1600)
    driver.set_page_load_timeout(50)
    actions = ActionChains(driver)
    wait = WebDriverWait(driver, 50)

    return driver, actions, wait


def find_in_url(url: str,
                item: int = -1,
                cleanup: bool = True) -> str:

    '''
    Partitions a URL (or any string) into a list of partitions partitioned by a forward slash.
    Replaces any non number/letter with a blank space if cleanup = True
    Returns element from partitioning list specified by item parameter.
    '''

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


def prepend_root_to_url(initial_url: str, prefix: str, subdomain: str = 'www') -> str:
    '''
    Adds base URL to truncated links which only contain a site filepath.
    For URL roots that are missing a subdomain, append the subdomain to the start of them.
    '''

    # If URL only provides path to page without Root URL, add the root
    if initial_url[:2] == '//':
        url = 'https:' + initial_url
    elif initial_url[0] == '/':
        url = prefix + initial_url
    else:
        url = initial_url

    # Some URLs have a custom subdomain instead of 'www.' In these cases, dont add the 'www' to the start
    url = make_https(url)
    if not url:
        url = prefix + '/' + initial_url
    elif not url.startswith(f'https://{subdomain}.') and len(get_url_components(url=url)) < 3:
        url = f'https://{subdomain}.' + url.removeprefix('https://')
    
    return url


def is_local_link(url: str, root_url: str) -> bool:
    '''
    Determines if a given URL links to another page within the same website or not.
    '''

    if root_url in url:
        return True
    else:
        return False


def is_external_link(url: str, root_url: str) -> bool:
    '''
    Determines if a given URL links to an external website or not.
    '''
    
    if url.startswith(root_url):
        return False
    if url.startswith('http'):
        return True
    else:
        return False


def try_getting_url_text(tag):
    '''
    Attempts to capture the text a given URL link is attached to on a webpage.
    Checks the 'text' element first, and if that is empty, then checks the 'string'
    Element.
    '''

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
    '''
    Finds the subdomain of the root site URL (ie. 'www').
    Needed to account for sites with custom subdomains.
    '''
    url_components = get_url_components(url=url)
    if len(url_components) >= 3: 
        sdomain = url_components[0]
    else:
        sdomain = 'www'
    
    return sdomain


def get_url_components(url: str) -> list:
    '''
    Returns a list of the 'pieces' of the root of a URL
    Pieces are defined as the strings separated by periods 
    between https:// and any trailing forward slash. 

    Example: 

    get_url_components(url='https://www.hello-world.com/newpage')
    returns:  ['www', 'hello-world', 'com']
    '''

    url_root = find_in_url(url=url, item=1, cleanup=False)
    url_comps = re.findall(r'[^\.]+', url_root)

    return url_comps


def closest_link_match(name, link_candidates, match_function= fuzz.token_sort_ratio) -> int:
    '''
    Compares a given link text (string) to a list of target keywords, then
    returns the fuzzy match score between that text and the most similar keyword.

    params: 
        name (String) : initial string
        link_candidates (List) : list of candidate strings
        
    returns: 
        the string with the smallest edit distance
    '''
    clst_url_score = 0
    for option in link_candidates:
        # similarity = match_function(name.lower(), option.lower().replace(' ', ''))
        if option.lower() in name.lower():
            return 100
        similarity = match_function(option.lower(), name.lower())
        if similarity > clst_url_score:
            clst_url_score = similarity
    
    return clst_url_score


def iterate_through_menus(drvr: webdriver.Chrome, actions: ActionChains) -> set:
    '''
    Simulates mouse and keyboard actions to open all dropdown and pop-up menus on a webpage, and collects 
    all the extra links that appear in these menus. 
    '''

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

if __name__ == '__main__':

    comp_word = ['Health Services', 'Public Surplus Auctions', 'Adult Education Center', 'Family Education Center','student', 'education', 'special education for family', 'Education for special need students']
    for word in comp_word:
        word = word#.replace(' ', '')
        print(word)
        print(closest_link_match(word, disability_keywords, match_function=fuzz.token_sort_ratio))
        print(closest_link_match(word, disability_link_keywords, match_function=fuzz.token_sort_ratio), '\n')