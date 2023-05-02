#!bin/python3
import argparse
import functools
import os
import shutil

import feedparser
import opml
import urllib3


# Remove characters that doesn't play well with 'nix and mac filesystems.'
def sanitize_filename(filename):
    return filename.replace('/', '-').replace(':', '')


# Small logger.
def the_logger(args, indent, message):
    if not args.silent:
        print('\t' * indent + message, flush=True)


def parse_args():
    # Setup command line arguments and description, etc.
    parser = argparse.ArgumentParser(description='Small utility to download complete podcasts from OPML files.')
    parser.add_argument('OPML', help='Path or URL to OPML file with podcasts.')
    parser.add_argument('-d', '--dir', nargs='?', help='Directory to save downloads in. Default is current directory')

    parser.add_argument('--limit-days', metavar='N', nargs=1, type=int,
                        help='Limit to downloading episodes newer than N days old. (Not implemented)')
    parser.add_argument('--limit-episodes', metavar='N', nargs=1, type=int,
                        help='Limit to downloading the N newest episodes.')
    parser.add_argument('--reverse', action='store_true',
                        help='Go through the entries in the RSS feeds en reverse order. (i.e. from old to new)')

    parser.add_argument('--delete-old', action='store_true',
                        help="Deletes any episode that does not fall within the limit parameters.")
    parser.add_argument('-r', '--reset', action='store_true',
                        help='Deletes contents of the download directory before downloading.')

    parser.add_argument('-s', '--silent', action='store_true', help='Silences log output to sceen.')
    parser.add_argument('-l', '--log', nargs=1, help='Saves log output to file.')
    return parser.parse_args()


def main():
    args = parse_args()
    logger = functools.partial(the_logger, args)

    # Ugly-ass hack for getting the file extension without having to regex through a url
    file_extensions = {'audio/mpeg': '.mp3', 'audio/x-m4a': '.m4a', 'audio/mpeg4-generic': '.mp4', 'audio/mp4': '.mp4',
                       'audio/ogg': '.ogg', 'audio/vorbis': '.ogg'}

    # Get podcast feeds from OPML file or URL
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
    for index_opml, opml_outline in enumerate(parsed_opml):
        # Read the RSS Feed from the 'xmlurl' attribute of the opml outline
        # We go through some trouble to normalize formatting of the attribute keys
        # since they are case-sensitive *sigh*  -.-
        opml_outline_keys = opml_outline._root.attrib.keys()
        rss_feed = None
        for _, key in enumerate(opml_outline_keys):
            if key.lower() == 'xmlurl':
                rss_feed = feedparser.parse(opml_outline._root.attrib[key])
                break

        if rss_feed is None:
            continue

        # Optionally go through the feed from old to new
        if args.reverse:
            rss_feed.entries.reverse()

        # Get the feed title, but sometimes the feed title isn't defined, in that case get it from the opml file
        # instead.
        try:
            rss_feed_title = rss_feed.feed.title
        except AttributeError:
            rss_feed_title = opml_outline.title

        logger(1,
               f'Downloading podcast {index_opml + 1}/{len(parsed_opml)}: {rss_feed_title} with {len(rss_feed.entries)} entries.')

        # Make the directory for the podcast
        # https://stackoverflow.com/questions/12517451/automatically-creating-directories-with-file-output
        os.chdir(download_dir)
        os.makedirs(rss_feed_title, exist_ok=True)
        os.chdir(rss_feed_title)
        existing_files = os.listdir()

        # Loop through each episode in the RSS feed
        for index_feed, entry in enumerate(rss_feed.entries):
            # Exit episode loop early if episode-limit is set and has been reached.
            if (args.limit_episodes is not None) and (index_feed >= args.limit_episodes[0]):
                continue
            # TODO: Exit episode loop early if days-limit is set and has been reached.
            # if (args.limit_days is not None) and

            # Go to next episode if there are no enclosures in the episode.
            if len(entry.enclosures) == 0:
                logger(2, f'No enclosure found in RSS entry, skipping {index_feed + 1}/{len(rss_feed.entries)}')
                continue

            year = f'{entry.published_parsed[0]:02}'
            month = f'{entry.published_parsed[1]:02}'
            day = f'{entry.published_parsed[2]:02}'
            date = f'{year}-{month}-{day}'
            audio_filename = f'[{date}] {entry.title}'

            # Get the url of the enclosed audio file
            try:
                enclosure_url = entry.enclosures[0].href
            except AttributeError:
                logger(2, f'No href found in RSS enclosure, skipping {index_feed + 1}/{len(rss_feed.entries)}')
                continue

            # Find the Content-Type type in the RSS enclosure
            file_extension = None
            filename = None
            try:
                file_extension = file_extensions.get(entry.enclosures[0].type, '')
                filename = sanitize_filename(audio_filename + file_extension)
            except AttributeError:
                pass

            # Skip download if the file already exists
            if any((sanitize_filename(audio_filename) == os.path.splitext(file)[0] for file in existing_files)):
                if file_extension is None:
                    logger(2, f'File already exists, skipping {index_feed + 1}/{len(rss_feed.entries)}: {audio_file}')
                else:
                    logger(2, f'File already exists, skipping {index_feed + 1}/{len(rss_feed.entries)}: {filename}')
                continue

            with http.request('GET', enclosure_url, preload_content=False) as r:
                if r.status not in range(200, 299):
                    if file_extension is None:
                        logger(2, f'Response had HTTP status {r.status}, skipping {index_feed + 1}/{len(rss_feed.entries)}: {audio_file}')
                    else:
                        logger(2, f'Response had HTTP status {r.status}, skipping {index_feed + 1}/{len(rss_feed.entries)}: {filename}')
                    continue

                # If the Content-Type couldn't be found in the enclosure, get it when downloading
                if file_extension is None or file_extension == '':
                    file_extension = file_extensions.get(r.headers['Content-Type'], '')
                    filename = sanitize_filename(audio_filename + file_extension)

                with open('temporary_download_file', 'wb') as audio_file:
                    logger(2, f'Downloading {index_feed + 1}/{len(rss_feed.entries)}: {filename}')
                    shutil.copyfileobj(r, audio_file)
                    os.rename('temporary_download_file', filename)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        exit(1)
