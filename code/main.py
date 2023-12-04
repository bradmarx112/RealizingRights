import pandas as pd
import logging
import os
from concurrent.futures.thread import ThreadPoolExecutor
import queue

from url_scraper.web_scraper import DistrictWebsiteScraper
from utilities.data_utils import format_input_district_df, format_output_df
from utilities.web_utils import MAX_THREAD_COUNT
from objects.scrape_lists import social_media_sites, disability_keywords, disability_link_keywords
from objects.exception_mgmt import PROCESS_ERROR_RSLT

__author__ = 'bmarx'

logger = logging.getLogger(__name__)

pipeline = queue.Queue()
full_df = pd.DataFrame()
urls_processed = 0

def main(source_info: dict, write_file_path: str, verbose: bool, max_dist_runs: int, col_subject: str, 
            reprocess_errors: bool = False, reprocess_empty: bool = False) -> None:
    global full_df
    logger.info(msg='BEGIN RUN')

    # Read in data
    xlsx_input = pd.read_excel(io=source_info['path'], sheet_name=source_info['sheet'], header=source_info['head_row'])
    district_df = format_input_district_df(dist_df=xlsx_input)

    # If the file to which we are writing exists (which happens when we process some, but not all, URLs),
    # Filter out the websites we have already evaluated from the input data.
    if os.path.isfile(write_file_path):
        out_file_df = pd.read_csv(write_file_path)
        if reprocess_errors:
            out_file_df = out_file_df[out_file_df[f'{col_subject} URL Text'] != PROCESS_ERROR_RSLT[1]]
            out_file_df.to_csv(write_file_path, index=False)
        if reprocess_empty:
            out_file_df = out_file_df[~out_file_df[f'{col_subject} URL Text'].isna()]
            out_file_df.to_csv(write_file_path, index=False)
        district_df = district_df.merge(out_file_df['District ID'], left_on='Agency ID', right_on='District ID', how='left')
        district_df = district_df[district_df['District ID'].isna()]
        district_df.drop('District ID', axis=1, inplace=True)

    district_df_to_use = district_df[:max_dist_runs]
    # Scrape data
    logger.info(msg='BEGIN WEB SCRAPE')
    
    url_list_to_process = list(district_df_to_use['URL'])
    num_urls = len(url_list_to_process)
    url_id_zip = [(url, a_id) for url, a_id in zip(list(district_df_to_use['URL']), list(district_df_to_use['Agency ID']))]

    with ThreadPoolExecutor(max_workers=MAX_THREAD_COUNT) as executor:

        _ = executor.submit(build_output_df, num_urls, col_subject)
        executor.map(scrape_district, url_id_zip)

    scanned_dist_df = full_df.merge(district_df, left_on='District ID', right_on='Agency ID')
    if os.path.isfile(write_file_path):
        scanned_dist_df.to_csv(write_file_path, mode='a', index=False, header=False)
    else:
        scanned_dist_df.to_csv(write_file_path, index=False)

    logger.info(msg='END RUN')


def scrape_district(url_id_tuple: tuple):
    global urls_processed
    print(f'Parsing {url_id_tuple[0]}...')
    try:
        district_scraper = DistrictWebsiteScraper(url=url_id_tuple[0],
                                                  agency_id=url_id_tuple[1], 
                                                  verbose=False,
                                                  boe_link_similarity_cutoff=80,
                                                  link_keywords=disability_link_keywords,
                                                  target_keywords=disability_keywords)
        district_scraper.find_board_meeting_and_social_media_links()
        district_scraper.drvr.quit()
        pipeline.put(district_scraper.url_data)
        # print(f'{url_id_tuple[0]} Done')
    except Exception as e:
        print(f"{url_id_tuple[0]} Error: {e}")

        pipeline.put({url_id_tuple[1]: PROCESS_ERROR_RSLT})


def build_output_df(num_urls: int, col_subject: str):
    global full_df
    global urls_processed
    while urls_processed < num_urls:
        url_info_dict = pipeline.get()
        url_info_row = format_output_df(url_data=url_info_dict,
                                        social_media_sites=social_media_sites, 
                                        col_subject=col_subject)
        full_df = full_df.append(url_info_row)
        urls_processed += 1
        print(urls_processed)


if __name__ == '__main__':
    source_info = {'path': 'data/USSchoolDistrictWebsiteInfo.xlsx', 'sheet': 'ELSI Export', 'head_row': 6}
    write_file_path = 'data/DisabilityOutput.csv'
    
    main(source_info=source_info, write_file_path=write_file_path, 
        verbose=False, max_dist_runs=6000, col_subject='Disability', reprocess_errors=True, reprocess_empty=False)
