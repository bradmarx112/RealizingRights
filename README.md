# RealizingRights
Repository for web scraping services used to support the 'Realizing Rights' research program at Brown University. Multithreaded application which crawls through school district websites to find the location on each website where school board meeting information is contained. Also tracks the presence of school district social media links. Outputs data to .csv.

## Requirements
- Python 3
- Conda

## Setup Instructions
1. Navigate to repo location and create conda environment
    - `conda env create -f env.yml`
2. Activate the new environment before running any code locally
    - `conda activate real_right_env`

## Running the Web Scraper
1. Save Excel/CSV output of school district information in the `/data` folder
2. Specify filepath of data from step 1 in the `source_info` dictionary in `main.py`
3. Specify filepath and file name of output data in `main.py`
4. Specify number of districts to process in the program with `max_dist_runs`
5. Run `main.py`