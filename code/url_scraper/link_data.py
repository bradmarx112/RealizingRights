import re
import logging

__author__ = 'bmarx'

logger = logging.getLogger(__name__)


class LinkData:
    def __init__(self, link_text: str, link_url: str, depth: int):
        self.link_text = link_text
        self.link_url = link_url.removesuffix('/')  #.lower()
        self.depth_found = depth
        self.num_url_sections = len(re.findall(r"[^/]+", self.link_url))

    def __eq__(self, other_link):
        return self.link_url == other_link.link_url

    def __hash__(self):
        return hash(self.link_url)

    def __repr__(self):
        return f'{self.link_text}: {self.link_url}'
