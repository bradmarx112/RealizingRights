import pandas as pd
import logging

from url_scraper.web_scraper import DistrictWebsiteScraper
from utilities.data_utils import format_input_district_df, format_output_boe_df
from objects.scrape_lists import social_media_sites

__author__ = 'bmarx'

logger = logging.getLogger(__name__)


def main(source_info: dict, write_file_path: str, verbose: bool, max_dist_runs: int) -> None:
    logger.info(msg='BEGIN RUN')

    # Read in data
    xlsx_input = pd.read_excel(io=source_info['path'], sheet_name=source_info['sheet'], header=source_info['head_row'])
    district_df = format_input_district_df(dist_df=xlsx_input)

    # Scrape data
    logger.info(msg='BEGIN WEB SCRAPE')
    district_scraper = DistrictWebsiteScraper(school_district_info_df=district_df, verbose=verbose)
    district_scraper.find_board_meeting_and_social_media_links(max_iters=5)

    dist_boe_info_df = format_output_boe_df(url_data=district_scraper.url_data, social_media_sites=social_media_sites)

    scanned_dist_df = dist_boe_info_df.merge(district_df, left_on='District ID', right_on='Agency ID')
    scanned_dist_df.to_csv(write_file_path)

    logger.info(msg='END RUN')


if __name__ == '__main__':
    source_info = {'path': 'data/USSchoolDistrictWebsiteInfo.xlsx', 'sheet': 'ELSI Export', 'head_row': 6}
    write_file_path = 'data/SampleOutput.csv'

    main(source_info=source_info, write_file_path=write_file_path, max_dist_runs=100)
