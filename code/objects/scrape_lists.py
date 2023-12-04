

# Do not process URLs that have any of these terms in them.
blacklist_terms = ['login', 'lightbox', 'file', '.pdf', '.doc', '.jpg', 'tel:', 'javascript', '@']
# , '.php' , '#'
# Phrases to look for in links that could contain board meeting URLs
boe_link_keywords = ['boe meeting', 'board meeting', 'board of education', 'parent', 'school board', 'board minutes', 'board',
                'meeting', 'video recording', 'board video recording', 'document', 'meeting agenda', 'meeting video', 'committee']

# Phrases to look for in the board meeting URL
board_meeting_keywords = ['boe meeting', 'board meeting', 'boe recording', 'board recording', 'minutes',
                            'boe meeting recording', 'board meeting recording', 'boe meeting video',
                            'board meeting video', 'boe video recording', 'board video recording']

# Social Media sites to check for
social_media_sites = ['youtube', 'vimeo', 'facebook', 'twitter']

# Phrases to look for in links that could contain board meeting URLs
disability_link_keywords = ['special education', 'sped', 'disability', 'parent', 'service', 'document', 'programs', 'department', 'disabilities', 
                            'exceptional student education', 'family', 'families', 'special need',  'exceptional', 'resources', 'pupil', 'support']

# Phrases to look for in the board meeting URL
disability_keywords = ['special education', 'special education service', 'student support', 'special education policy', 'disability', 'disabilities', 'exceptional child', 
                        'academic support service', 'exceptional student education', 'special need', 'special service', 'exceptional education',
                         'special program', 'student service', 'special population', 'pupil service']
