from concurrent.futures.thread import ThreadPoolExecutor
import os.path
import sys
import pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from collections import defaultdict
from utilities.web_assist import (prepend_root_to_url, make_context, get_soup_from_html, find_in_url,
                                  get_website_chunk_by_class, format_dict_from_soup)
from datetime import datetime as dt
import logging
import re
import queue

__author__ = 'bmarx'

logger = logging.getLogger(__name__)


class SchoolWebsiteScraper:

    def __init__(self,
                 school_district_info_df: pd.DataFrame,
                 search_site: str = 'https://search.brave.com/search?q=',
                 page_limit: int = 100,
                 dump_limit: int = 150
                 ):
        self.base_url = search_site
        self.district_info_df = school_district_info_df
        self.website_page_limit = page_limit
        self.dump_limit = dump_limit
        self._context = make_context()
        self.query_strings = self.generate_query_strings()
        self._scanned_sites = 0

    def _format_search_term(self, row) -> str:
        if 'school' not in row['DISTRICT NAME']:
            return row['DISTRICT NAME'] + ' school district ' + row['NMCNTY']
        else:
            return row['DISTRICT NAME'] + ' ' + row['NMCNTY']

    def generate_query_strings(self):
        self.district_info_df['DISTRICT NAME'] = self.district_info_df['DISTRICT NAME'].str.lower()
        self.district_info_df['NMCNTY'] = self.district_info_df['NMCNTY'].str.lower()
        self.district_info_df['search_term'] = self.district_info_df.apply(lambda x: self._format_search_term(x), axis=1)

        return self.district_info_df['search_term']


if __name__ == '__main__':
    input_data = pd.read_csv('data\school_district_info.csv')
    sws = SchoolWebsiteScraper(school_district_info_df = input_data)