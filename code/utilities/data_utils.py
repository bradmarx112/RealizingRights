import pandas as pd
import logging

from utilities.web_utils import (prepend_root_to_url, make_https)

__author__ = 'bmarx'

logger = logging.getLogger(__name__)


def format_input_district_df(dist_df: pd.DataFrame) -> pd.DataFrame:
    '''
    Formats dataframe imported from csv file into form appropriate for downstream web scraping.
    '''
    # Ensure URL uses https protocol
    try:
        dist_df['URL'] = dist_df['URL'].apply(lambda x: make_https(url=x))

        # Only consider districts with >0 students and schools associated
        dist_df['NumStudents'] = pd.to_numeric(dist_df['NumStudents'], errors='coerce')
        dist_df = dist_df[dist_df['NumSchools'] > 0].reset_index(drop=True)

    except:
        logger.error(msg='Provided dataframe is malformed! Unable to process.')
        return dist_df

    dist_df = dist_df[dist_df['NumStudents'] > 0]
    # Ignore districts without any URL
    dist_df = dist_df[~dist_df['URL'].isna()]
    
    # Make lowercase and add 'www' to URLs where applicable
    dist_df['URL'] = dist_df['URL'].apply(lambda x: prepend_root_to_url(base_url=x.lower(), prefix=''))

    return dist_df


def format_output_boe_df(url_data: dict, social_media_sites: list) -> pd.DataFrame:
    '''
    Converts dictionary output of web scraping process into dataframe suitable for export.
    '''
    df_cols = ['District ID', 'Board Meeting URL Text', 'Board Meeting URL Link', 'Board Meeting Link Depth'] + social_media_sites
    boe_df = pd.DataFrame(columns=df_cols)

    for url, data in url_data.items():
        init_row = {
            'District ID': url,
            'Board Meeting URL Text': data[1],
            'Board Meeting URL Link': data[2],
            'Board Meeting Link Depth': data[3]
        }

        row = {key: init_row.get(key, None) for key in [*init_row, *social_media_sites]}

        if data[0]:
            row.update(data[0])

        boe_df = boe_df.append(row, ignore_index=True)

    return boe_df
