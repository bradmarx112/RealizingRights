from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

import queue
import os.path
import sys
import pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utilities.web_utils import (prepend_root_to_url, make_driver_utils, find_in_url, is_local_link, iterate_through_menus,
                                  is_external_link, try_getting_url_text, get_subdomain, closest_link_match)
from datetime import datetime as dt
import logging

# currentdir = os.path.dirname(os.path.realpath(__file__))
# parentdir = os.path.dirname(currentdir)
# gparentdir = os.path.dirname(parentdir)
# sys.path.append(parentdir)
# sys.path.append(gparentdir)

from url_scraper.link_data import LinkData
from objects.scrape_lists import blacklist_terms, link_keywords, board_meeting_keywords, social_media_sites

__author__ = 'bmarx'

logger = logging.getLogger(__name__)


class DistrictWebsiteScraper:

    def __init__(self,
                 url: str,
                 agency_id: str,
                 site_link_relevance_cutoff: int = 90,
                 boe_link_similarity_cutoff: int = 60,
                 blacklist_terms: list = blacklist_terms, 
                 link_keywords: list = link_keywords, 
                 board_meeting_keywords: list = board_meeting_keywords, 
                 social_media_sites: list = social_media_sites,
                 verbose: bool = False
                 ):

        # Dataframe with District URLs and other info
        self.url = url
        self.agency_id = agency_id

        # Integer cutoffs for string similarity scoring
        self.site_link_relevance_cutoff = site_link_relevance_cutoff
        self.boe_link_similarity_cutoff = boe_link_similarity_cutoff

        # Lists of terms for filtering and similarity scoring
        self.blacklist_terms = blacklist_terms
        self.link_keywords = link_keywords
        self.board_meeting_keywords = board_meeting_keywords
        self.social_media_sites = social_media_sites

        # Utilities for Selenium driver
        self.drvr, self.actions, self.wait = make_driver_utils()
        self.drvr.set_page_load_timeout(15)
        self.verbose = verbose

        self.url_data = {}


    def find_board_meeting_and_social_media_links(self) -> None:

        start_link_set = set()
        dist_info = []
        start_link_set.add(LinkData(link_text='BASE', link_url=self.url, depth=0))
        recursed_lcl_links, recursed_ext_links = set(), set()
        recursed_lcl_links, recursed_ext_links = self._recurse_scan_all_unique_links_in_site(url=self.url,
                                                                                        base_url=self.url, 
                                                                                        local_link_set=start_link_set,
                                                                                        external_link_set=set())

        cur_sim = self.boe_link_similarity_cutoff
        best_link = None
        all_links = recursed_lcl_links
        all_links.update(recursed_ext_links)
        all_links_sorted = sorted(list(all_links), key=lambda x: x.depth_found)
        ext_links_sorted = sorted(list(recursed_ext_links), key=lambda x: x.depth_found)

        # look for the most likely board meeting link across all links
        for link in all_links_sorted:
            if cur_sim == 100:
                break
            if not link.link_text:
                continue

            sim = closest_link_match(link.link_text, self.board_meeting_keywords)
            if sim > cur_sim:
                best_link = link
                cur_sim = sim

        # Identify External Links Pointing to social media sites 
        sites_identified = {}
        num_ext_links = len(ext_links_sorted)
        ext_id = 0

        # Temp assignment because we pop from this list every iteration
        social_media_sites = self.social_media_sites.copy()
        while ext_id < num_ext_links:
            ext_link = ext_links_sorted[ext_id]
            scl_id = 0
            while scl_id < len(social_media_sites):
                if social_media_sites[scl_id] in ext_link.link_url:
                    sites_identified[social_media_sites.pop(scl_id)] = ext_link.depth_found
                scl_id += 1

            ext_id += 1

            if len(social_media_sites) == 0:
                break
        
        if best_link:
            self.url_data[self.agency_id] = (sites_identified, best_link.link_text, best_link.link_url, best_link.depth_found)
        else: 
            self.url_data[self.agency_id] = (sites_identified, None, None, None)
                
        logger.info(msg='District URL processing complete')
        

    def _recurse_scan_all_unique_links_in_site(self, url: str, base_url: str, 
                                                local_link_set: set = set(),
                                                external_link_set: set = set(),
                                                depth: int = 0,
                                                subdomain: str = 'www'):

        # First, try to get the web page.
        try:
            self.drvr.get(url)
        except:
            return set(), set()

        # Wait for the page to be fully loaded
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Dont bother with '404 error' pages
        if self.drvr.title.lower() == 'page not found':
            return set(), set()

        if self.verbose:
            print(f'Depth {depth} for {url}')

        soup = BeautifulSoup(self.drvr.page_source, 'html.parser')
        # Find all Links on page
        raw_links = set(soup.find_all("a"))

        if depth == 0:
            # Accounting for redirects to other url names
            subdomain = get_subdomain(url=self.drvr.current_url)
            base_url = prepend_root_to_url(base_url=self.drvr.current_url, prefix='', subdomain=subdomain)
            base_url = find_in_url(url=base_url, item=0, cleanup=False) + '//' + find_in_url(url=base_url, item=1, cleanup=False) 
            url = base_url
            # Find links in drop down menus. Assuming the menus appear on every page so only get them the first time
            menu_links = iterate_through_menus(drvr=self.drvr, actions=self.actions)
            raw_links.update(menu_links)

        # Classify each raw link as either internal or external
        new_local_link_set, external_link_set = self._classify_raw_links(raw_links=raw_links, 
                                                                        external_link_set=external_link_set, 
                                                                        base_url=base_url, 
                                                                        subdomain=subdomain,
                                                                        depth=depth)

        # Only pick up links that did not appear in any other page seen so far
        new_links = new_local_link_set - local_link_set
        # Add those links to set of current links, but if they already exist do not overwrite previous instance
        local_link_set.update(new_local_link_set)
        # Sort links to iterate over by 'depth' (How many sections between slashes there are)
        new_links_sorted = sorted(list(new_links), key=lambda x: x.num_url_sections)
            
        for link in new_links_sorted:
            # if self.verbose:
            #     print(' '*(depth+1) + '|_' + str(depth) + ': ' + str(len(local_link_set)))
            # Recursion time
            recursed_lcl_links, recursed_ext_links = self._recurse_scan_all_unique_links_in_site(url=link.link_url, 
                                                                                            base_url=base_url,
                                                                                            local_link_set=local_link_set,
                                                                                            external_link_set=external_link_set,
                                                                                            depth=depth + 1,
                                                                                            subdomain=subdomain)
            local_link_set.update(recursed_lcl_links)
            external_link_set.update(recursed_ext_links)

        return local_link_set, external_link_set


    def _classify_raw_links(self, raw_links: list, external_link_set: set, base_url: str, subdomain: str, depth: int):
        # Compare new local links to old so we dont enter an infinite loop of links!
        new_local_link_set = set()
        for raw_link in raw_links:
            try:
                # Only pick up links with valid URL structure
                link_url = raw_link.attrs['href']
                # Skip blacklisted terms 
                if any([term in link_url.lower() for term in self.blacklist_terms]):
                    continue
                link_url = prepend_root_to_url(link_url, base_url, subdomain=subdomain)
            except:
                continue
            
            # Extract the text shown on the webpage for the link
            link_text = try_getting_url_text(raw_link)
            
            if is_external_link(link_url, base_url):
                if link_text:
                    boe_relevance_score = closest_link_match(link_text, self.board_meeting_keywords)
                else:
                    boe_relevance_score = 0
                # Only capture external links if they are social media links or related to BOE meetings
                if any([site in link_url.lower() for site in self.social_media_sites]) \
                    or boe_relevance_score > self.boe_link_similarity_cutoff:

                    external_link_set.add(LinkData(link_text, link_url, depth=depth))

            # Add link to proper set
            elif is_local_link(link_url, base_url):
                if not link_text:
                    continue
                # Score how similar the text is to keywords that can potentially house links to BOE meetings
                link_relevance_score = closest_link_match(name=link_text, link_candidates=self.link_keywords)
                if link_relevance_score > self.site_link_relevance_cutoff:
                    new_local_link_set.add(LinkData(link_text, link_url, depth=depth))

        return new_local_link_set, external_link_set


if __name__ == '__main__':

    start_url = 'https://www.srvusd.net'

    test_scraper = DistrictWebsiteScraper(url=start_url, agency_id=1000, verbose=True)
    test_scraper.find_board_meeting_and_social_media_links()
    print(test_scraper.url_data)