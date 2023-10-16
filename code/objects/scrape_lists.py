

# Do not process URLs that have any of these terms in them.
blacklist_terms = ['login', 'lightbox', 'file', '.php', '#', '.pdf', '.doc', '.jpg', 'tel:', 'javascript', '@']

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
disability_link_keywords = ['special education', 'disability', 'disability rights', 'parent', 'disability service', 
                            'special education service', 'document', 'program']

# Phrases to look for in the board meeting URL
disability_keywords = ['special education', 'disability', 'disability rights', 'disability service', 'special education service',
                        'disability policy', 'special education policy', 'disability program', 'special education program']
