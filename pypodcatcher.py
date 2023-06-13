import os, sys, pathlib, tempfile, shutil, traceback
import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from email.utils import parsedate_to_datetime as parse_date

from lxml import etree
from lxml.etree import ElementTree
import httpx


def parse_args():
    # Setup command line arguments and description, etc.
    parser = argparse.ArgumentParser(
        prog='pypodcatcher.py',
        description='Small utility to download complete podcasts from OPML files.'
    )
    parser.add_argument('opml', action='store',   help='Path to OPML.')
    parser.add_argument('-d', '--dir', nargs='?', help='Directory to save downloads in. Default is current directory')

    parser.add_argument('--limit', metavar='N', type=int,
                        help='Only download first N items from each feed.')
    parser.add_argument('--skip', metavar='N', type=int,
                        help='Skip first N items from each feed.')
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='Reverse the feed, i.e. oldest first.')
    parser.add_argument('--reset', action='store_true',
                        help='Deletes contents of the download directory before downloading.')

    return parser.parse_args()


@dataclass
class FeedOutline:
    type: str
    text: str
    title: str
    htmlUrl: str
    xmlUrl: str

    def __key(self):
        return self.type, self.text, self.title, self.htmlUrl, self.xmlUrl

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, FeedOutline):
            return self.__key() == other.__key()
        return NotImplemented


@dataclass
class FeedItem:
    outline: FeedOutline
    guid: str
    title: str
    link: str
    date: date
    enclosure_url: str
    enclosure_mime: str

    def filename(self) -> str:
        return sanitize_filename(f'[{self.date}] {self.title}.{self.__extension()}')

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, FeedItem):
            return self.__key() == other.__key()
        return NotImplemented

    def __key(self):
        return (
            self.guid, self.title, self.link, self.date,
            self.enclosure_url, self.enclosure_mime,
        )

    def __extension(self) -> str:
        # Getting the file extension without having to regex through an url
        return {
            'audio/mpeg': 'mp3',
            'audio/x-m4a': 'm4a',
            'audio/mpeg4-generic': 'mp4',
            'audio/mp4': 'mp4',
            'audio/ogg': 'ogg',
            'audio/vorbis': 'ogg'
        }.get(self.enclosure_mime, 'mp3')


class FeedDownloader:
    # Basic design from mCoding https://www.youtube.com/watch?v=ftmdDlwMwwQ

    def __init__(
            self,
            outlines: Iterable[FeedOutline],
            client: httpx.AsyncClient,
            save_dir: pathlib.Path,
            reverse: bool,
            limit: int,
            skip: int,
            workers: int = 10,
    ):
        self.start_items = set(outlines)
        self.client = client
        self.todo: asyncio.Queue[FeedOutline | FeedItem] = asyncio.Queue()

        self.seen = set()
        self.done = set()

        self.save_dir = save_dir
        self.reverse = reverse
        self.limit = limit
        self.skip = skip
        self.num_workers = workers

    async def run(self):
        await self.on_found_items(self.start_items)  # prime the queue
        workers = [asyncio.create_task(self.worker()) for _ in range(self.num_workers)]
        await self.todo.join()

        for worker in workers:
            worker.cancel()

    async def worker(self):
        while True:
            try:
                await self.process_one()
            except asyncio.CancelledError:
                return

    async def process_one(self):
        task_item = await self.todo.get()

        try:
            if isinstance(task_item, FeedOutline):
                feed_outline = task_item
                await self.fetch_feed_items(feed_outline)
            elif isinstance(task_item, FeedItem):
                feed_item = task_item
                await self.fetch_feed_enclosures(feed_item)
            else:
                assert False, "unreachable type(task_item)"
        except Exception as e:
            print(f'exception occurred for {type(task_item)} titled "{task_item.title}" at line {sys.exc_info()[2].tb_lineno} {e.__repr__()}')
            traceback.print_tb(sys.exc_info()[2])
            # TODO: retry handling here...
            pass
        finally:
            self.todo.task_done()

    async def fetch_feed_items(self, outline: FeedOutline):
        outline_print = f'{outline.title}'
        message = 'fetching feed items'
        print(f'{outline_print} :::: {message}')

        # TODO: rate limit here...
        #   self.num_workers takes care of total connections
        #   but connections per domain should also be limited
        #   as well as connections per time
        await asyncio.sleep(2.0)

        response = await self.client.get(outline.xmlUrl, follow_redirects=True)

        if response.status_code not in range(200, 300):
            message = f'fetching failed with http status {response.status_code}'
            print(f'{outline_print} :::: {message}')
            return

        feed: ElementTree = etree.fromstring(response.read(), base_url=outline.xmlUrl)
        feed_elements = feed.findall("./channel/item[enclosure]")
        message = f'found {len(feed_elements)} items with enclosures'
        print(f'{outline_print} :::: {message}')

        feed_items = [
            FeedItem(
                outline=outline,
                guid=element.findtext('guid'),
                title=element.findtext('title'),
                link=element.findtext('link'),
                date=parse_date(element.findtext('pubDate')).date(),
                enclosure_url=element.find('enclosure').get('url'),
                enclosure_mime=element.find('enclosure').get('type')
            )
            for element in feed_elements
        ]

        if self.reverse:
            feed_items.reverse()
        if self.skip:
            feed_items = feed_items[self.skip:]
        if self.limit:
            feed_items = feed_items[:self.limit]

        await self.on_found_items(set(feed_items))

    async def fetch_feed_enclosures(self, item: FeedItem):
        outline_print = f'{item.outline.title}'
        item_print = f'[{item.date}] {item.title}'
        message = 'fetching feed enclosure'
        print(f'{outline_print} :::: {item_print} :::: {message}')

        # TODO: rate limit here...
        #   self.num_workers takes care of total connections
        #   but connections per domain should also be limited
        #   as well as connections per time
        await asyncio.sleep(2.0)

        url: str = item.enclosure_url
        feed_name: str = item.outline.title
        filename: str = item.filename()

        feed_dir = self.save_dir.joinpath(feed_name)
        feed_dir.mkdir(parents=True, exist_ok=True)
        real_path = feed_dir.joinpath(filename)
        if real_path.exists():
            print(f'{outline_print} :::: {item_print} :::: skipped fetching enclosure')
            return

        response = await self.client.get(url, follow_redirects=True)

        temp_fd, temp_path = tempfile.mkstemp(dir=feed_dir)
        with open(temp_fd, 'wb') as temp_file:
            for chunk in response.iter_bytes():
                temp_file.write(chunk)
            os.rename(src=temp_path, dst=real_path)

        print(f'{outline_print} :::: {item_print} :::: finished fetching enclosure')

    async def on_found_items(self, items: set[FeedOutline | FeedItem]):
        new = items - self.seen
        self.seen.update(new)

        for item in new:
            await self.put_todo(item)

    async def put_todo(self, item: FeedOutline | FeedItem):
        await self.todo.put(item)


def outlines_from_opml(opml_path):
    with open(opml_path, 'r') as f:
        opml: ElementTree = etree.parse(f)
        feeds = opml.findall("//outline[@type='rss']")
    for feed in feeds:
        yield FeedOutline(**{key: feed.get(key) for key in feed.keys()})
    return


def sanitize_filename(filename: str) -> str:
    # Remove characters that doesn't play well with 'nix and mac filesystems.'
    return filename.replace('/', '-').replace(':', '')


async def main():
    args = parse_args()

    # Setup download directory
    download_dir = pathlib.Path(args.dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    # Delete download directory contents if reset option is given.
    if args.reset:
        for root, dirs, files in os.walk(download_dir):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))

    task_queue = asyncio.Queue()

    outlines = outlines_from_opml(args.opml)
    downloader = FeedDownloader(
        outlines=outlines,
        client=httpx.AsyncClient(),
        save_dir=download_dir,
        reverse=args.reverse,
        limit=args.limit,
        skip=args.skip,
    )

    await downloader.run()


if __name__ == '__main__':
    asyncio.run(main())
