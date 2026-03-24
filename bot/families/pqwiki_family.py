import os

from pywikibot.family import Family

_MEDIAWIKI_HOST = os.environ.get("WIKI_MEDIAWIKI_HOST", "mediawiki")


class Family(Family):
    name = "pqwiki"

    langs = {
        "en": _MEDIAWIKI_HOST,
    }
    
    def scriptpath(self, code):
        return ''
    
    def protocol(self, code):
        return 'http'