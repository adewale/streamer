from pshb import ContentParser, Post, PostFactory
from streamer import Subscription

import datetime
import feedparser
import pshb
import streamer
import unittest

class StubHubSubscriber(pshb.HubSubscriber):
  def unsubscribe(self, url, hub, callback_url):
    self.url = url
    self.hub = hub
    self.callback_url = callback_url

class SubscriptionTest(unittest.TestCase):
  def setUp(self):
    subscriptions = Subscription.all()
    for subscription in subscriptions:
      subscription.delete()

  def testCanTellIfFeedIsAlreadyStored(self):
    url = "http://example.org/atom"
    s = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    s.put()

    self.assertTrue(Subscription.exists(url))

  def testCanTellIfFeedIsNew(self):
    url = "http://example.org/atom"
    self.assertFalse(Subscription.exists(url))

  def testAddingSubscriptionTwiceOnlyAddsOneRecordToDataStore(self):
    url = "http://example.org/atom"
    s = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    s.put()
    self.assertEquals(1, len(Subscription.find(url).fetch(1000)))
    s2 = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    s2.put()
    self.assertEquals(1, len(Subscription.find(url).fetch(1000)))
    self.assertEquals(1, Subscription.all().count())

  def testCanDeleteSubscription(self):
    url = "http://example.org/atom"
    s = Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    s.put()
    self.assertTrue(Subscription.exists(url))
    Subscription.deleteSubscriptionWithMatchingUrl(url)
    self.assertFalse(Subscription.exists(url))

class BackgroundHandlerTest(unittest.TestCase):
  def testCanDeleteFeed(self):
    url = "http://example.org/atom"
    s = streamer.Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    s.put()

    streamer.handleDeleteSubscription(url, hubSubscriber=StubHubSubscriber())
    self.assertFalse(Subscription.exists(url))

  def testDeletingFeedUnsubscribesFromHub(self):
    url = "http://example.org/atom"
    hub="http://hub.example.org/"
    s = streamer.Subscription(url=url, hub=hub, sourceUrl="http://example.org/", key_name=url)
    s.put()

    hubSubscriber=StubHubSubscriber()
    streamer.handleDeleteSubscription(url, hubSubscriber=hubSubscriber)
    self.assertEquals(url, hubSubscriber.url)
    self.assertEquals(hub, hubSubscriber.hub)
    self.assertEquals('http://streamer-ade.appspot.com/posts', hubSubscriber.callback_url)