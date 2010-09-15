"""Everything you need to subscribe to PSHB feeds on AppEngine

This module depends on the existence of:
settings.py containing various config parameters as constants
feedparser.py to parse feeds
"""

from google.appengine.ext import db
from google.appengine.api import urlfetch

import datetime
import feedparser
import logging
import pprint
import settings
import urllib

class PostFactory(object):
  """A factory for Posts.

  This avoids having to over-ride AppEngine's __init__ method in order to convert a FeedParser entry into a type that can be stored in the DataStore. Solutions like using an Expando won't work because many of the FeedParser types are things like time.struct_time which don't map cleanly onto built-in DataStore types."""

  @staticmethod
  def __extractUniqueId(entry):
  # TODO(ade) Change this to a normal class rather than use staticmethod everywhere

    if hasattr(entry, 'id') and not isinstance(entry.id, dict):
    # We have to check that the id isn't a dictionary because GReader feeds
    # have multiple ids which FeedParser turns into a dictionary
      return entry.id
    elif hasattr(entry, 'link'):
      return entry.link
    else:
      raise ValueError("Entry with no unique identifier: %s" % pprint.pformat(entry))

  @staticmethod
  def createPost(url, feedUrl, title, content, datePublished, author, entry):
    uniqueId = PostFactory.__extractUniqueId(entry)

    logging.debug("Unique id is: %s for entry: %s" % (uniqueId, pprint.pformat(entry)))
    entryString = repr(entry)

    return Post(key_name=uniqueId, url=url, feedUrl=feedUrl, title=title, content=content, datePublished=datePublished,
                author=author, entryString=entryString)

class Post(db.Model):
  """An atom:entry or RSS item."""
  url = db.StringProperty(required=True)
  feedUrl = db.StringProperty(required=True)
  title = db.StringProperty(multiline=True)
  content = db.TextProperty()
  datePublished = db.DateTimeProperty()
  author = db.StringProperty()
  entryString = db.TextProperty()

  def getFeedParserEntry(self):
    entry = eval(self.entryString)
    return entry

  @property
  def day(self):
    return self.datePublished.strftime('%A %B %d, %Y')

  @staticmethod
  def deleteAllPostsWithMatchingFeedUrl(url):
    postsQuery = db.GqlQuery("SELECT __key__ from Post where feedUrl= :1", url)
    for postKey in postsQuery.fetch(settings.MAX_FETCH):
      db.delete(postKey)

class UrlError(Exception):
  def __init__(self, url, status_code, response_string):
    self.url = url
    self.status_code = status_code
    self.response_string = response_string

  def __str__(self):
    return 'url: %s status code: %d response:<%s>' % (self.url, self.status_code, self.response_string)

class ContentParser(object):
  """A parser that extracts data from PSHB feeds

  It uses the FeedParser library to parse the feeds, extracts information about the PSHB hub being used and creates valid Streamer Posts."""

  def __init__(self, content, defaultHub='https://pubsubhubbub.appspot.com/', alwaysUseDefaultHub=False, urlToFetch=""):
    if urlToFetch:
      response = urlfetch.fetch(urlToFetch)
      logging.info("Status was: [%s]" % response.status_code)
      if response.status_code == 404 or response.status_code == 400:
        raise UrlError(urlToFetch, response.status_code, str(response))
      content = response.content
    self.data = feedparser.parse(content)
    self.defaultHub = defaultHub
    self.alwaysUseDefaultHub = alwaysUseDefaultHub

  def dataValid(self):
    if self.data.bozo:
      return False
    else:
      return True

  def logErrors(self):
    logging.error('Bad feed data. %s: %r', self.data.bozo_exception.__class__.__name__, self.data.bozo_exception)

  def __createDateTime(self, entry):
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
      return datetime.datetime(*(entry.updated_parsed[0:6]))
    else:
      return datetime.datetime.utcnow()

  def __extractLink(self, entryOrFeed, relName):
    if not hasattr(entryOrFeed, 'links'):
      logging.warning("Object doesn't have links: %s" % str(entryOrFeed))
      return None
    for link in entryOrFeed.links:
      if link['rel'] == relName:
        return str(link['href'])
    return None

  def __extractAtomPermaLink(self, entryOrFeed):
    if hasattr(entryOrFeed, 'links'):
      link = self.__extractLink(entryOrFeed, 'alternate')
      if link:
        return link
    return entryOrFeed.get('id', '')

  def __extractAuthor(self, entryOrFeed):
  # Get the precise name of the author if we can
    if hasattr(entryOrFeed, 'author_detail'):
      author = entryOrFeed['author_detail']['name']
    else:
      author = entryOrFeed.get('author', '')
    return author

  def __extractPost(self, entry):
    if hasattr(entry, 'content'):
      link = self.__extractAtomPermaLink(entry)
      title = entry.get('title', '')
      content = entry.content[0].value
      #Workaround for Flickr's RSS feeds. I should probably ignore it but they use RSS 2.0 as their default format.
      #TODO(ade) Check to see if this is actually a bug in Feedparser.py since arguably rss2.0:description elements should be mapped to atom:content elements.
      if not content:
        content = entry.get('summary', '')
      datePublished = self.__createDateTime(entry)

      author = self.__extractAuthor(entry)
    else:
      logging.debug("Entry has no atom:content")
      link = entry.get('link', '')
      title = entry.get('title', '')
      content = entry.get('description', '')
      datePublished = self.__createDateTime(entry)
      author = ""
    feedUrl = self.extractFeedUrl()
    return PostFactory.createPost(url=link, feedUrl=feedUrl, title=title, content=content, datePublished=datePublished,
                                  author=author, entry=entry)

  def extractFeedAuthor(self):
    author = self.__extractAuthor(self.data.feed)
    if not author:
    # Get the authors of all the entries and if they're the same assume that author made all the entries.
    # TODO(ade) This and the extractAuthor method don't correctly handle situations where a feed or an entry has multiple authors.
    # We currently get away with this because I haven't added multiple author support to feedparser.py
      authors = [self.__extractAuthor(entry) for entry in self.data.entries]
      if len(set(authors)) > 1:
        return ""
      return authors[0]
    return author

  def extractPosts(self):
    postsList = []
    for entry in self.data.entries:
      p = self.__extractPost(entry)
      postsList.append(p)
    return postsList

  def extractHub(self):
    if self.alwaysUseDefaultHub:
      return self.defaultHub

    hub = self.__extractLink(self.data.feed, 'hub')
    if hub is None:
      return self.defaultHub
    else:
      return hub

  def extractFeedUrl(self):
    for link in self.data.feed.links:
      if link['rel'] == 'http://schemas.google.com/g/2005#feed' or link['rel'] == 'self':
        return link['href']
    else:
      return self.data.feed.link + "rss"

  def extractSourceUrl(self):
    sourceUrl = self.__extractAtomPermaLink(self.data.feed)
    return sourceUrl


class HubSubscriber(object):
  def subscribe(self, url, hub, callback_url):
    self._talk_to_hub('subscribe', url, hub, callback_url)

  def unsubscribe(self, url, hub, callback_url):
    self._talk_to_hub('unsubscribe', url, hub, callback_url)

  def _talk_to_hub(self, mode, url, hub, callback_url):
    parameters = {"hub.callback": callback_url,
                  "hub.mode": mode,
                  "hub.topic": url,
                  "hub.verify": "async", # We don't want un/subscriptions to block until verification happens
                  "hub.verify_token": settings.SECRET_TOKEN, #TODO Must generate a token based on some secret value
    }
    payload = urllib.urlencode(parameters)
    response = urlfetch.fetch(hub,
                              payload=payload,
                              method=urlfetch.POST,
                              headers={'Content-Type': 'application/x-www-form-urlencoded'})
    logging.info("Status of %s for feed: %s at hub: %s is: %d" % (mode, url, hub, response.status_code))
    if response.status_code != 202:
      logging.info(response.content)
