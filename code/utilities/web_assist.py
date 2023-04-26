from bs4 import BeautifulSoup
import ssl
import urllib.parse
from urllib.request import urlopen
from retry import retry
import re
import warnings
import Levenshtein as lev
from typing import Union
from bs4.element import NavigableString
import logging


__author__ = 'bmarx'

logger = logging.getLogger(__name__)


def make_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


@retry(tries=5)
def get_soup_from_html(qry: str, ct, prefix: str = 'https://search.brave.com/search?q=', timeout: float = 30):
    formatted_url = prefix + urllib.parse.quote_plus(qry)
    with urlopen(formatted_url, context=ct, timeout=timeout) as html:
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
    return url


def get_website_chunk_by_class(soup: BeautifulSoup, tag: str, classname: str = None):

    if classname is None:
        sect = soup.find_all(tag)
    else:
        sect = soup.find_all(tag, class_=classname)
    return sect


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


def closest_link_match(name, link_candidates) -> str:
    '''
    Calculate Levenshtein distance between one url and all urls in a list. Returns the url from the list
    that has the smallest edit distance. If the smallest distance is greater than the threshold, no url is returned.
    
    params: 
        name (String) : url that is incorrect
        link_candidates (List) : list of urls that are known to be correct.
        
    returns: 
        the correct url (as a string) with the smallest edit distance
    '''
    closest_link = None
    clst_url_score = len(name) + 1
    for option_tuple in link_candidates:
        option = option_tuple[1]
        similarity = lev.distance(name.lower(), option.lower())
        if similarity < clst_url_score:
            closest_link = option_tuple[0]
            clst_url_score = similarity
    
    return closest_link


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


if __name__ == '__main__':
    ct = make_context()
    test_sp = get_soup_from_html(qry='Alaska Gateway School District Southeast Fairbanks Census Area', ct=ct)
    chunk = get_website_chunk_by_class(soup=test_sp, tag='a', classname='result-header')
    out_tuple_list = []
    for qry_rslt in chunk:
        url = qry_rslt.attrs['href']
        link_desc = qry_rslt.text
        if 'wikipedia' in url or '.com' in url:
            continue
        desc_cln = re.findall(r'[^\n]+', link_desc)[0]
        out_tuple_list.append((url, desc_cln))
    best = closest_link_match(name='Alaska Gateway School District', link_candidates=out_tuple_list)

    print('done')
