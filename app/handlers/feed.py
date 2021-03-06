from feedgen.feed import FeedGenerator

import uuid
import handlers
from handlers.pager import QueryPager
from models.package import Package
import cherrypy
from datetime import datetime

XML_BEGIN = '<?xml version="1.0" encoding="UTF-8"?>'


class Feeds(object):
    """Generation of Feeds"""

    @staticmethod
    def generate_feed(page=1):
        feed = FeedGenerator()
        feed.id("https://pub.dartlang.org/feed.atom")
        feed.title("Pub Packages for Dart")
        feed.link(href="https://pub.dartlang.org/", rel="alternate")
        feed.link(href="https://pub.dartlang.org/feed.atom", rel="self")
        feed.description("Last Updated Packages")
        feed.author({"name": "Dart Team"})
        i = 1
        pager = QueryPager(int(page), "/feed.atom?page=%d",
                           Package.all().order('-updated'),
                           per_page=10)
        for item in pager.get_items():
            i += 1
            entry = feed.add_entry()
            for author in item.latest_version.pubspec.authors:
                entry.author({"name": author[0]})
            entry.title("v" + item.latest_version.pubspec.get("version") +\
                " of " + item.name)
            entry.link(link={"href": "https://pub.dartlang.org/packages/" +\
                item.name, "rel": "alternate", "title": item.name})
            entry.id(uuid.uuid5(uuid.NAMESPACE_URL,
                ("https://pub.dartlang.org/packages/" + item.name + "#" +\
                item.latest_version.pubspec.get("version")).encode('utf-8')).urn)
            entry.description(
                item.latest_version.pubspec
                .get("description", "Not Available"))
            readme = item.latest_version.readme_obj
            if readme is not None:
                entry.content(readme.render(), type='html')
            else:
                entry.content("<p>No README Found</p>", type='html')
        return feed

    def atom(self, page=1):
        cherrypy.response.headers['Content-Type'] = "application/atom+xml"
        return XML_BEGIN + "\n" +\
            self.generate_feed(page=page).atom_str(pretty=True)
