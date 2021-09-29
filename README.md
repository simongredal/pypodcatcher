# py-podcatcher
Small utility to backup podcasts audio files from OPML file

py-podcatcher will save each podcast in it's own directory, and audio files will be named acording to title and date in the RSS-feed.

## Installing/Running
This script is using Python version 3.  
You need to have `python` and `pip` installed.  


I recommend running this in a virtual-env like so:

``` sh
cd py-podcatcher/

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python pypodcatcher.py --help
```

## Notes
Not all the options listed in the help text are actually implemented yet.
