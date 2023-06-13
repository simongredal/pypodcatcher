# pypodcatcher
Small utility to backup podcasts audio files from OPML file

pypodcatcher will save each podcast in its own directory, and audio files will be
named according to title and date in the RSS-feed.


## Example
An opml file like this
```xml
<?xml version="1.0"?>
<opml version="1.0">
    <head>
        <title>Podcast Subscriptions</title>
    </head>
    <body>
        <outline type="rss" text="Podcast A" title="Podcast A" xmlUrl="https://www.example.com/episodes?format=rss" htmlUrl="https://www.example.com/" />
		<outline type="rss" text="Podcast B" title="Podcast B" xmlUrl="https://www.example.com/rss.xml" htmlUrl="https://www.example.com/" />
		<outline type="rss" text="Podcast C" title="Podcast C" xmlUrl="https://www.example.com/feed" htmlUrl="https://www.example.com/" />
	</body>
</opml>
```


Will result in a file structure like this
```
├── Podcast A
│   ├── [2020-12-03] 001 Hey.mp3
│   └── [2020-12-17] 002 Bye.mp3
├── Podcast B
│   ├── [2015-10-28] 3 Onwards.mp3
│   ├── [2015-11-12] 4 Upwards.mp3
└── Podcast C
    ├── [2023-01-12] Episode 8 “Snare!”.m4a
    └── [2023-02-08] Episode 9 “Hi-Hat!”.m4a
```


## Installing/Running
You need to have `python` and `pip` installed.

This script uses async/awaits features so it requires at least on Python v3.5+,
but I have only tested it on Python v3.11.

I recommend running this in a virtual-env like so:
```shell
cd py-podcatcher/

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python pypodcatcher.py --help
```


## Usage
```
usage: pypodcatcher.py [-h] [-d [DIR]] [--limit N] [--skip N] [-r] [--reset] [-s] [-l LOG] opml

Small utility to download complete podcasts from OPML files.

positional arguments:
  opml                  Path to OPML.

options:
  -h, --help            show this help message and exit
  -d [DIR], --dir [DIR]
                        Directory to save downloads in. Default is current directory
  --limit N             Only download first N items from each feed.
  --skip N              Skip first N items from each feed.
  -r, --reverse         Reverse the feed, i.e. oldest first.
  --reset               Deletes contents of the download directory before downloading.
```


## TODO
- [ ] Improve logging. It's kind of chatty, and also very jumbled due to the async nature.
It will probably require inspecting the workers and asyncio.Task's through a
separate thread and updating a curses display, or something to that effect.
- [ ] Improve error handling, and retry handling. Investigate why downloads sometimes timeout.
