#!/usr/bin/env python3

import feedparser, opml, urllib3
import os, shutil, argparse



# Setup command line arguments and description, etc.
parser =  argparse.ArgumentParser(description='Small utility to download complete podcasts from OPML files.')
parser.add_argument('OPML', help='Path or URL to OPML file with podcasts.')
parser.add_argument('-d', '--dir', nargs='?', help='Directory to save downloads in. Default is current directory')

parser.add_argument('--limit-days', metavar='N', nargs=1, type=int, help='Limit to downloading episodes newer than N days old.')
parser.add_argument('--limit-episodes', metavar='N', nargs=1, type=int, help='Limit to downloading the N newest episodes.')

parser.add_argument('--delete-old', action='store_true', help="Deletes any episode that does not fall within the limit parameters.")
parser.add_argument('-r', '--reset', action='store_true', help='Deletes contents of the download directory before downloading.')

parser.add_argument('-s', '--silent', action='store_true', help='Silences log output to sceen.')
parser.add_argument('-l', '--log', nargs=1, help='Saves log output to file.')
args = parser.parse_args()

# Ugly-ass hack for getting the file extension without trying to regex through a url
file_extensions = {'audio/mpeg': '.mp3'}

def sanitize_filename(filename):
	return filename.replace('/', '-').replace(':', '')

def logger(message):
	if not args.silent:
		print(message)

# Get podcast feeds from OPML
parsed_opml = opml.parse(args.OPML)

# Setup current working directory.
if args.dir is not None:
	os.makedirs(args.dir, exist_ok=True)
	os.chdir(args.dir)
download_dir = os.getcwd()

# Delete directory contents if reset option is given.
if args.reset:
	for root, dirs, files in os.walk(download_dir):
		for f in files:
			os.unlink(os.path.join(root, f))
		for d in dirs:
			shutil.rmtree(os.path.join(root, d))

# Set up urllib
http = urllib3.PoolManager()
urllib3.disable_warnings()

# Go through each feed
for index, opml_outline in enumerate(parsed_opml):
	rss_feed = feedparser.parse(opml_outline.xmlUrl)
	
	logger(f'Downloading podcast {index+1}/{len(parsed_opml)}: {rss_feed.feed.title} with {len(rss_feed.entries)} entries.')
	
	# Make the directory for the podcast
	# https://stackoverflow.com/questions/12517451/automatically-creating-directories-with-file-output
	os.chdir(download_dir)
	os.makedirs(rss_feed.feed.title, exist_ok=True)
	os.chdir(rss_feed.feed.title)
	
	for index, entry in enumerate(rss_feed.entries):
		year = f'{entry.published_parsed[0]:02}'
		month = f'{entry.published_parsed[1]:02}'
		day = f'{entry.published_parsed[2]:02}'
		date=f'{year}-{month}-{day}'
		audio_filename = f'{date} | {entry.title}'
		
		if len(entry.enclosures) > 0:
			try:
				enclosure_url = entry.enclosures[0].href
			except AttributeError:
				logger(f'No href found in RSS enclosure, skipping {index+1}/{len(rss_feed.entries)}')
				continue
			
			try:
				file_extension = file_extensions.get(entry.enclosures[0].type, '')
			except AttributeError:
				pass
				
			if file_extension != '':
				filename = sanitize_filename(audio_filename+file_extension)
			
				if os.path.exists(filename):
					logger(f'File already exists, skipping {index+1}/{len(rss_feed.entries)}: {filename}')
				else:
					with http.request('GET', enclosure_url, preload_content=False, ) as r, open(filename, 'wb') as audio_file:
						logger(f'Downloading {index+1}/{len(rss_feed.entries)}: {filename}')
						shutil.copyfileobj(r, audio_file)
			else:
				with http.request('GET', enclosure_url, preload_content=False, ) as r:
					file_extension = file_extensions.get(r.headers['Content-Type'], '')
					filename = sanitize_filename(audio_filename+file_extension)
					
					if os.path.exists(filename):
						logger(f'File already exists, skipping {index+1}/{len(rss_feed.entries)}: {filename}')
					else:
						with open(filename, 'wb') as audio_file:
							logger(f'Downloading {index+1}/{len(rss_feed.entries)}: {filename}')
							shutil.copyfileobj(r, audio_file)
			
		else:
			logger(f'No enclosure found in RSS entry, skipping {index+1}/{len(rss_feed.entries)}')