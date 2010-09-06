from pshb import ContentParser, Post, PostFactory
from streamer import Subscription

import datetime
import feedparser
import settings
import unittest

class SubscriptionTest(unittest.TestCase):
  def setUp(self):
    subscriptions = Subscription.all()
    for subscription in subscriptions:
      subscription.delete()

  def testCanTellIfFeedIsAlreadyStored(self):
    url = "http://example.org/atom"
    f = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    f.put()

    self.assertTrue(Subscription.exists(url))

  def testCanTellIfFeedIsNew(self):
    url = "http://example.org/atom"
    self.assertFalse(Subscription.exists(url))

  def testAddingSubscriptionTwiceOnlyAddsOneRecordToDataStore(self):
    url = "http://example.org/atom"
    f = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    f.put()
    self.assertEquals(1, len(Subscription.find(url).fetch(1000)))
    f2 = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    f2.put()
    self.assertEquals(1, len(Subscription.find(url).fetch(1000)))
    self.assertEquals(1, Subscription.all().count())

  def testCanDeleteSubscription(self):
    url = "http://example.org/atom"
    f = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    f.put()
    self.assertTrue(Subscription.exists(url))
    Subscription.deleteSubscriptionWithMatchingUrl(url)
    self.assertFalse(Subscription.exists(url))

class PostTest(unittest.TestCase):
  def testCanDeleteMatchingPostsCreatedUsingPostFactory(self):
    feedUrl = "some feed url"
    entry1 = feedparser.FeedParserDict({'id':feedUrl})
    p1 = PostFactory.createPost(url='someurl', feedUrl=feedUrl, title='title', content=None, datePublished=None,
                                author=None, entry=entry1)
    p1.put()

    otherFeedUrl = "other feed url"
    entry2 = feedparser.FeedParserDict({'id':otherFeedUrl})
    p2 = PostFactory.createPost(url='someurl', feedUrl=otherFeedUrl, title='title', content=None, datePublished=None,
                                author=None, entry=entry2)
    p2.put()

    self.assertEquals(2, len(Post.all().fetch(2)))
    Post.deleteAllPostsWithMatchingFeedUrl(feedUrl)
    self.assertEquals(1, len(Post.all().fetch(2)))

    allPosts = Post.all().fetch(2)
    self.assertEquals(p2.feedUrl, allPosts[0].feedUrl)
    self.assertEquals(1, len(allPosts))

  def testAddingPostTwiceOnlyAddsOneRecordToDataStore(self):
    feedUrl = "some feed url"
    entry1 = feedparser.FeedParserDict({'id':feedUrl})
    p1 = PostFactory.createPost(url='someurl', feedUrl=feedUrl, title='title', content=None, datePublished=None,
                                author=None, entry=entry1)
    p1.put()

    p2 = PostFactory.createPost(url='someurl', feedUrl=feedUrl, title='title', content=None, datePublished=None,
                                author=None, entry=entry1)
    p2.put()
    self.assertEquals(1, Post.all().count())

  def testCanGenerateHumanReadableDatesFromDateObjects(self):
    feedUrl = "some feed url"
    entry1 = feedparser.FeedParserDict({'id':feedUrl})
    publishedDate = datetime.datetime(2010, 7, 4)
    p1 = PostFactory.createPost(url='someurl', feedUrl=feedUrl, title='title', content=None, datePublished=publishedDate
                                , author=None, entry=entry1)
    expectedDay = 'Sunday July 04, 2010'
    self.assertEquals(expectedDay, p1.day)


  # TODO(ade) Write a runtests.py and move this test into it's own module

class ContentParserTest(unittest.TestCase):
  SAMPLE_FEED = open("test_data/sample_entries").read()
  BLOGGER_FEED = open("test_data/blogger_feed").read()
  HUBLESS_FEED = open("test_data/hubless_feed").read()
  FEEDBURNER_FEED = open("test_data/feedburner_feed").read()
  RSS_FEED = open("test_data/rss_feed").read()
  RSS_FEED_WITHOUT_LINKS = open("test_data/rss_feed_without_links").read()
  CANONICAL_RSS_FEED = open("test_data/canonical_rss_feed").read()
  VALID_ATOM_FEED = open("test_data/valid_atom_feed").read()
  NO_AUTHOR_RSS_FEED = open("test_data/no_author_rss_feed").read()
  MULTI_AUTHOR_FEED = open("test_data/multi_author_feed").read()
  NO_UPDATED_ELEMENT_FEED = open("test_data/no_updated_element_feed").read()
  FLICKR_RSS_FEED = open("test_data/flickr_rss_feed").read()
  GREADER_FEED = open("test_data/greader_feed").read()
  BUZZ_FEED = open("test_data/buzz_feed").read()

  def testCanExtractCorrectNumberOfPostsFromFeedWithMissingUpdatedElement(self):
    parser = ContentParser(self.NO_UPDATED_ELEMENT_FEED)
    posts = parser.extractPosts()
    self.assertTrue(parser.dataValid())
    self.assertEquals(1, len(posts))

  def testCanIdentifyPostsWithGoodData(self):
    parser = ContentParser(self.SAMPLE_FEED)
    parser.extractPosts()
    self.assertTrue(parser.dataValid())

  def testCanIdentifyPostsWithBadData(self):
    parser = ContentParser("Bad data that isn't an atom entry")
    parser.extractPosts()
    self.assertFalse(parser.dataValid())

  def testCanExtractCorrectNumberOfPostsFromSampleFeed(self):
    parser = ContentParser(self.SAMPLE_FEED)
    posts = parser.extractPosts()
    self.assertEquals(2, len(posts))

  def testExtractedPostsHaveOriginalEntry(self):
    parser = ContentParser(self.SAMPLE_FEED)
    posts = parser.extractPosts()
    self.assertTrue(posts[0].getFeedParserEntry())
    self.assertEqual(posts[0].content, posts[0].getFeedParserEntry()['content'][0]['value'])

  def testCanExtractPostsWithExpectedContentFromSampleFeed(self):
    parser = ContentParser(self.SAMPLE_FEED)
    posts = parser.extractPosts()
    self.assertEquals("This is the content for random item #460920825", posts[0].content)
    self.assertEquals("http://pubsubhubbub-loadtest.appspot.com/foo/460920825", posts[0].url)
    self.assertEquals("http://pubsubhubbub-loadtest.appspot.com/feed/foo", posts[0].feedUrl)
    self.assertEquals("This is the content for random item #695555168", posts[1].content)
    self.assertEquals("http://pubsubhubbub-loadtest.appspot.com/foo/695555168", posts[1].url)
    self.assertEquals("http://pubsubhubbub-loadtest.appspot.com/feed/foo", posts[1].feedUrl)

  def testCanExtractPostWithExpectedContentFromFlickrRssFeed(self):
    parser = ContentParser(self.FLICKR_RSS_FEED)
    posts = parser.extractPosts()
    self.assertEquals(
        """<p><a href="http://www.flickr.com/people/adewale_oshineye/">adewale_oshineye</a> posted a photo:</p>\n\t\n<p><a href="http://www.flickr.com/photos/adewale_oshineye/4589378281/" title="47: First past the post"><img alt="47: First past the post" height="160" src="http://farm5.static.flickr.com/4048/4589378281_265c641ebb_m.jpg" width="240" /></a></p>"""
        , posts[0].content)

  def testExtractsAtomIdFromGReaderFeeds(self):
    parser = ContentParser(self.GREADER_FEED)
    posts = parser.extractPosts()
    self.assertEquals("http://www.flickr.com/photos/chewie007/4519889183/", posts[0].key().name())
    self.assertEquals("http://www.youtube.com/watch?v=Ma9lzcUe2Zg&feature=autoshare", posts[1].key().name())

  def testCanExtractPostFromRssFeed(self):
    parser = ContentParser(self.RSS_FEED)
    posts = parser.extractPosts()
    self.assertEquals("Gnome to Split Off from GNU Project?", posts[0].title)
    self.assertEquals('<a href="http://news.ycombinator.com/item?id=991627">Comments</a>', posts[0].content)

  def testCanExtractMoreDataFromCanonicalRssFeed(self):
    parser = ContentParser(self.CANONICAL_RSS_FEED)
    posts = parser.extractPosts()
    self.assertEquals("RSS for BitTorrent, and other developments", posts[0].title)
    self.assertEquals("http://www.scripting.com/stories/2009/12/06/rssForBittorrentAndOtherDe.html", posts[0].url)
    self.assertEquals(datetime.datetime(*((2009, 12, 6, 23, 19, 25, 6, 340, 0)[0:6])), posts[0].datePublished)
    #TODO Find out if there's a better way to handle the RSS author element
    self.assertEquals("", posts[0].author)

  def testCanExtractPostsWithExpectedLinksFromBloggerFeed(self):
    parser = ContentParser(self.BLOGGER_FEED)
    posts = parser.extractPosts()
    self.assertEquals("http://blog.oshineye.com/2009/12/25-we-are-all-in-gutter-but-some-of-us.html", posts[0].url)
    self.assertEquals("http://blog.oshineye.com/2009/12/scalecamp-uk-2009.html", posts[1].url)
    self.assertEquals("http://blog.oshineye.com/2009/10/heuristic-outcomes.html", posts[2].url)

  def testCanExtractPostsWithExpectedAuthorNameFromBloggerFeed(self):
    parser = ContentParser(self.BLOGGER_FEED)
    posts = parser.extractPosts()
    self.assertEquals("Ade", posts[0].author)

  def testCanExtractAuthorNameFromBloggerFeed(self):
    parser = ContentParser(self.BLOGGER_FEED)
    self.assertEquals("Ade", parser.extractFeedAuthor())

  def testCanExtractAuthorNameFromValidAtomFeedWithNoTopLevelAuthor(self):
    parser = ContentParser(self.VALID_ATOM_FEED)
    self.assertEquals("Enrique Comba Riepenhausen", parser.extractFeedAuthor())

  def testCanExtractAuthorNameViaDublinCoreCreatorFromRssFeed(self):
    parser = ContentParser(self.NO_AUTHOR_RSS_FEED)
    self.assertEquals("Chris", parser.extractFeedAuthor())

  def testDoesNotExtractAuthorFromFeedWithMultipleAuthors(self):
    parser = ContentParser(self.MULTI_AUTHOR_FEED)
    self.assertEquals("", parser.extractFeedAuthor())

  def testCanExtractHubFromFeed(self):
    parser = ContentParser(self.BLOGGER_FEED)
    hub = parser.extractHub()
    self.assertEquals("http://pubsubhubbub.appspot.com/", hub)

  def testCanOverrideHubForFeed(self):
    fakeDefaultHub = 'http://example.org/fake-url-for-hub'
    parser = ContentParser(self.BLOGGER_FEED, defaultHub=fakeDefaultHub)
    self.assertNotEquals(fakeDefaultHub, parser.extractHub())

    parser.alwaysUseDefaultHub = True
    self.assertEquals(fakeDefaultHub, parser.extractHub())

  def testCanExtractHubFromFeedburnerFeeds(self):
    self.assertEquals("http://pubsubhubbub.appspot.com", ContentParser(self.FEEDBURNER_FEED).extractHub())
    self.assertEquals("http://pubsubhubbub.appspot.com/", ContentParser(self.NO_UPDATED_ELEMENT_FEED).extractHub())

  def testCanExtractDefaultHubForHubLessFeeds(self):
    parser = ContentParser(self.HUBLESS_FEED)
    hub = parser.extractHub()
    self.assertEquals(parser.defaultHub, hub)

  def testCanExtractFeedUrls(self):
    self.assertEquals("http://pubsubhubbub-loadtest.appspot.com/feed/foo",
                      ContentParser(self.SAMPLE_FEED).extractFeedUrl())
    self.assertEquals("http://blog.oshineye.com/feeds/posts/default", ContentParser(self.BLOGGER_FEED).extractFeedUrl())
    self.assertEquals("http://en.wikipedia.org/w/index.php?title=Special:RecentChanges&feed=atom",
                      ContentParser(self.HUBLESS_FEED).extractFeedUrl())
    self.assertEquals("http://feeds.feedburner.com/PlanetTw", ContentParser(self.FEEDBURNER_FEED).extractFeedUrl())
    self.assertEquals("http://news.ycombinator.com/rss", ContentParser(self.RSS_FEED).extractFeedUrl())
    self.assertEquals("http://www.scripting.com/rss", ContentParser(self.CANONICAL_RSS_FEED).extractFeedUrl())
    self.assertEquals("http://feeds.feedburner.com/ChrisParsons",
                      ContentParser(self.NO_UPDATED_ELEMENT_FEED).extractFeedUrl())
    self.assertEquals("https://www.googleapis.com/buzz/v1/activities/105037104815911535953/@public?alt=atom",
                      ContentParser(self.BUZZ_FEED).extractFeedUrl())

  def testCanExtractSourceUrls(self):
    self.assertEquals("http://pubsubhubbub-loadtest.appspot.com/foo", ContentParser(self.SAMPLE_FEED).extractSourceUrl()
                      )
    self.assertEquals("http://blog.oshineye.com/", ContentParser(self.BLOGGER_FEED).extractSourceUrl())
    self.assertEquals("http://en.wikipedia.org/wiki/Special:RecentChanges",
                      ContentParser(self.HUBLESS_FEED).extractSourceUrl())
    self.assertEquals("http://blogs.thoughtworks.com/", ContentParser(self.FEEDBURNER_FEED).extractSourceUrl())
    self.assertEquals("http://news.ycombinator.com/", ContentParser(self.RSS_FEED).extractSourceUrl())
    self.assertEquals("http://www.scripting.com/", ContentParser(self.CANONICAL_RSS_FEED).extractSourceUrl())
    self.assertEquals("http://chrismdp.github.com/", ContentParser(self.NO_UPDATED_ELEMENT_FEED).extractSourceUrl())
