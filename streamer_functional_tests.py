import os
import unittest

from gaetestbed import FunctionalTestCase

import pshb
import settings
import streamer

# Set the environment so that tests which require admin privileges, and thus look up the user's email address, will pass
# See: http://code.google.com/p/nose-gae/issues/detail?id=13 for more
os.environ['AUTH_DOMAIN'] = 'example.org'
os.environ['USER_EMAIL'] = 'example@example.org'
os.environ['USER_ID'] = 'example' # Our test user is logged in
settings.OPEN_ACCESS = True #Make the Admin pages visible to all

class BaseSubscriptionHandlerTest(FunctionalTestCase, unittest.TestCase):
  def assertOKAfterRedirect(self, response, expectedString=None):
  # Response should be a redirect that takes the user to a sensible page
    self.assertRedirects(response)
    response = response.follow()
    self.assertOK(response)
    if expectedString:
      response.mustcontain(expectedString)

class SubscriptionsHandlerTest(BaseSubscriptionHandlerTest):
  APPLICATION = streamer.application

  def testCanShowSubscriptions(self):
    response = self.get('/subscriptions')
    self.assertOK(response)
    response.mustcontain("<title>Subscriptions</title>")

  def testCanDetectEmptySubscription(self):
    response = self.post('/subscriptions', data={}, expect_errors=True)
    self.assertEquals('500 Internal Server Error', response.status)

  def testCanAddNewSubscriptionUsingTaskQueue(self):
    data = {'function':'handleNewSubscription', 'url':'http://blog.oshineye.com/feeds/posts/default', 'nickname':'ade'}
    response = self.post('/bgtasks', data=data, expect_errors=True)
    self.assertEqual(1, streamer.Subscription.all().count())

  def testAddingNewSubscriptionsUsingTaskQueueIsIdempotent(self):
    data = {'function':'handleNewSubscription', 'url':'http://blog.oshineye.com/feeds/posts/default', 'nickname':'ade'}
    self.assertEqual(streamer.Subscription.all().count(), 0)
    response = self.post('/bgtasks', data=data, expect_errors=True)
    self.assertEqual(streamer.Subscription.all().count(), 1)
    response = self.post('/bgtasks', data=data, expect_errors=True)
    self.assertEqual(streamer.Subscription.all().count(), 1)

  def testAddingNoneExistentFeedsDoesNotRaiseAnException(self):
    data = {'function':'handleNewSubscription', 'url':'http://www.oshineye.com/404FromStreamer', 'nickname':'ade'}
    response = self.post('/bgtasks', data=data, expect_errors=True)
    self.assertEquals('200 OK', response.status)

  def testDeletingFeedDoesNotRaiseAnException(self):
    url = "http://example.org/atom"
    f = streamer.Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
    f.put()

    data = {'function':'handleDeleteSubscription', 'url': url, 'nickname':'ade'}
    response = self.post('/bgtasks', data=data, expect_errors=True)
    self.assertEquals('200 OK', response.status)

  def testEnqueuesTaskForNewSubscription(self):
    data = {'url':'http://blog.oshineye.com/feeds/posts/default'}
    self.assertTasksInQueue(0)
    response = self.post('/subscriptions', data=data)
    self.assertTasksInQueue(1)
    self.assertOKAfterRedirect(response, "<title>Subscriptions</title>")

class PostsHandlerTest(FunctionalTestCase, unittest.TestCase):
  APPLICATION = streamer.application

  def testCanShowPosts(self):
    response = self.get('/posts')
    self.assertOK(response)
    response.mustcontain("<title>Posts</title>")

  def testGoingToSlashIsTheSameAsPostsPage(self):
    responseFromPostsPage = self.get('/posts')
    responseFromSlash = self.get('/')
    self.assertEquals(responseFromPostsPage.body, responseFromSlash.body)
    self.assertEquals(responseFromPostsPage.status, responseFromSlash.status)

  def testCanAcceptHubChallengeForSubscriptionToExistingFeed(self):
    url = "http://example.org/atom"
    hub="http://hub.example.org/"
    s = streamer.Subscription(url=url, hub=hub, sourceUrl="http://example.org/", key_name=url)
    s.put()

    challenge = 'some hub challenge message'
    response = self.get('/posts?hub.mode=subscribe&hub.topic=%s&hub.challenge=%s' % (url, challenge))
    self.assertOK(response)
    response.mustcontain(challenge)

  def testAcceptsHubChallengeForUnsubscriptionToDeletedFeed(self):
    # If the hub wants us to unsubscribe and we don't have the subscription then we should accept it
    url = "http://example.org/atom"

    challenge = 'some hub challenge message'
    response = self.get('/posts?hub.mode=unsubscribe&hub.topic=%s&hub.challenge=%s' % (url, challenge))
    self.assertOK(response)
    response.mustcontain(challenge)

  def testRejectsHubChallengeForUnsubscriptionToExistingFeed(self):
    # If the hub wants us to unsubscribe and we have the subscription then the hub is probably confused
    # so we honour the intentions of our users since they'll think we're still subscribed
    url = "http://example.org/atom"
    hub="http://hub.example.org/"
    s = streamer.Subscription(url=url, hub=hub, sourceUrl="http://example.org/", key_name=url)
    s.put()

    challenge = 'some hub challenge message'
    response = self.get('/posts?hub.mode=unsubscribe&hub.topic=%s&hub.challenge=%s' % (url, challenge), expect_errors=True)
    self.assertEquals('404 Not Found', response.status)
    response.mustcontain("Challenge failed for feed: %s with mode: %s" % (url, 'unsubscribe'))

class AboutHandlerTest(FunctionalTestCase, unittest.TestCase):
  APPLICATION = streamer.application

  def testCanShowAboutPage(self):
    response = self.get('/about')
    self.assertOK(response)
    response.mustcontain("<title>About</title>")

class AdminRefreshSubscriptionsHandlerTest(BaseSubscriptionHandlerTest):
  APPLICATION = streamer.application

  def testCanShowRefreshSubscriptionsPage(self):
    response = self.get('/admin/refreshSubscriptions')
    self.assertOKAfterRedirect(response, '<title>Subscriptions</title>')

  def testEnqueuesTaskPerSubscription(self):
    self.assertTasksInQueue(0)
    for i in range(5):
      url = "http://example.org/atom" + str(i)
      f = streamer.Subscription(url=url, hub="http://hub.example.org/", sourceUrl="http://example.org/", key_name=url)
      f.put()
    self.get('/admin/refreshSubscriptions')
    self.assertTasksInQueue(streamer.Subscription.all().count())

class AdminAddSubscriptionHandlerTest(FunctionalTestCase, unittest.TestCase):
  APPLICATION = streamer.application

  def testCanShowAddSubscriptionPage(self):
    response = self.get('/admin/addSubscription')
    self.assertOK(response)
    response.mustcontain("<title>Add Subscription</title>")

class AdminDeleteSubscriptionHandlerTest(FunctionalTestCase, unittest.TestCase):
  APPLICATION = streamer.application

  def testCanShowDeleteSubscriptionPage(self):
    response = self.get('/admin/deleteSubscription')
    self.assertOK(response)
    response.mustcontain("<title>Delete Subscription</title>")

  # TODO(ade) Write a runtests.py and move this test into it's own module

class ContentParserFunctionalTest(unittest.TestCase):
  def testCanExtractPostsFromRemoteSite(self):
    parser = pshb.ContentParser(None, urlToFetch="http://blog.oshineye.com/feeds/posts/default")
    posts = parser.extractPosts()
    self.assertTrue(len(posts) > 2)