# py-podcatcher
Small utility to backup podcasts audio files from OPML file

py-podcatcher will save each podcast in it's own directory, and audio files will be named acording to title and date in the RSS-feed.

## Installing/Running
This script is using Python version 3.  
You need to have `python` and `pip` installed.  


I recommend running this in a virtual-env like so:

```sh
cd py-podcatcher/

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python pypodcatcher.py --help
```

## Notes
Not all the options listed in the help text are actually implemented yet.

## TODO

- [ ] Don't do a HEAD request to figure out file extension when comparing filenames, it' slow
- [ ] Fix podcast counter being stuck at 4 out of some number
- [ ] Do asynchronous fetching with threads or queues  or generators or something
- [ ] Structure code better
- [ ] Flush when logging