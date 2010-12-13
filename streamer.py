from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import login_required
from google.appengine.ext.webapp.util import run_wsgi_app

import logging
import os
import pshb
import settings

from google.appengine.api.labs import taskqueue

class BackGroundTaskHandler(webapp.RequestHandler):
  def post(self):
    logging.info("Request body %s" % self.request.body)
    retryCount = self.request.headers.get('X-AppEngine-TaskRetryCount')
    taskName = self.request.headers.get('X-AppEngine-TaskName')
    if retryCount and int(retryCount) > settings.MAX_TASK_RETRIES:
      logging.warning("Abandoning this task: %s after %s retries" % (taskName, retryCount))
      return
    functionName = self.request.get('function')
    logging.info("Background task being executed. Function is: <%s>" % (functionName))
    if functionName == 'handleNewSubscription':
      handleNewSubscription(self.request.get('url'), self.request.get('nickname'))


class Subscription(db.Model):
  """A record of a PSHB lease."""
  url = db.StringProperty(required=True)
  hub = db.StringProperty(required=True)
  sourceUrl = db.StringProperty(required=True)

  # Nickname of the person who added this feed to the system
  subscriber = db.StringProperty()
  # Automatically work out when a feed was added
  dateAdded = db.DateTimeProperty(auto_now_add=True)
  author = db.StringProperty()

  @staticmethod
  def find(url):
    """Return a Query object so that the caller can choose how many results should be fetched"""
    # This query only fetches the key because that's faster and computationally cheaper.
    query = db.GqlQuery("SELECT __key__ from Subscription where url= :1", url)

    return query

  @staticmethod
  def exists(url):
    """Return True or False to indicate if a subscription with the given url exists"""
    query = Subscription.find(url)
    return len(query.fetch(1)) > 0

  @staticmethod
  def deleteSubscriptionWithMatchingUrl(url):
    query = db.GqlQuery("SELECT __key__ from Subscription where url= :1", url)
    # We deliberately use a large fetch value to ensure we delete all feeds matching that URL
    for key in query.fetch(settings.MAX_FETCH):
      db.delete(key)


def render(out, htmlPage, templateValues={}):
  templateValues['admin'] = userIsAdmin()
  path = os.path.join(os.path.dirname(__file__), htmlPage)
  out.write(template.render(path, templateValues))

def getAllSubscriptionsAsTemplateValues():
# Get all the feeds
  subscriptions = db.GqlQuery('SELECT * from Subscription ORDER by url')

  # Render them in the template
  templateValues = {'subscriptions': subscriptions}
  return templateValues

def userIsAdmin():
  user = users.get_current_user()
  # Only admin users can see this page
  if settings.OPEN_ACCESS or (user and users.is_current_user_admin()):
    return True
  return False

class BaseAdminHandler(webapp.RequestHandler):
  def addNewSubscription(self, url):
    user = users.get_current_user()
    nickname = user.nickname()
    # This is basically calling handleNewSubscription(url, nickname) in the background
    taskqueue.add(url='/bgtasks', params={'function': 'handleNewSubscription', 'url':url, 'nickname':nickname})

class AdminRefreshSubscriptionsHandler(BaseAdminHandler):
  @login_required
  def get(self):
  # Only admin users can see this page
    if userIsAdmin():
      query = Subscription.all()
      for subscription in query.fetch(settings.MAX_FETCH):
        logging.info("Refreshing subscription: %s " % subscription.url)
        self.addNewSubscription(subscription.url)
      self.redirect('/subscriptions')
    else:
      self.error(403)
      self.response.out.write("You are not the Admin")

class AdminAddSubscriptionHandler(webapp.RequestHandler):
  @login_required
  def get(self):
  # Only admin users can see this page
    if userIsAdmin():
      templateValues = getAllSubscriptionsAsTemplateValues()
      render(self.response.out, 'add_subscriptions.html', templateValues)
    else:
      self.error(403)
      self.response.out.write("You are not the Admin")

class AdminDeleteSubscriptionHandler(webapp.RequestHandler):
  @login_required
  def get(self):
  # Only admin users can see this page
    if userIsAdmin():
      templateValues = getAllSubscriptionsAsTemplateValues()
      render(self.response.out, 'delete_subscriptions.html', templateValues)
    else:
      self.error(403)
      self.response.out.write("You are not the Admin")

  def post(self):
  # Only admin users can see this page
    if userIsAdmin():
      url = self.request.get('url')
      logging.info("Url: %s" % url)
      if url:
        handleDeleteSubscription(url)
      self.redirect('/admin/deleteSubscription')
    else:
      self.error(403)
      self.response.out.write("You are not the Admin")

class AboutHandler(webapp.RequestHandler):
  def get(self):
    render(self.response.out, 'about.html')

  # TODO work out to make the handle* functions deferred

def handleDeleteSubscription(url, hubSubscriber=pshb.HubSubscriber()):
  logging.info("Deleting subscription: %s" % url)

  pshb.Post.deleteAllPostsWithMatchingFeedUrl(url)
  subscription = Subscription.get_by_key_name(url)
  logging.info('Found: %s' % str(subscription))

  Subscription.deleteSubscriptionWithMatchingUrl(url)
  hubSubscriber.unsubscribe(url, subscription.hub, "http://%s.appspot.com/posts" % settings.APP_NAME)

def handleNewSubscription(url, nickname):
  logging.info("Subscription added: <%s> by <%s>" % (url, nickname))
  # TODO test this function directly just like we do for handleDeleteSubscription

  try:
    parser = pshb.ContentParser(None, settings.DEFAULT_HUB, settings.ALWAYS_USE_DEFAULT_HUB, urlToFetch=url)
  except pshb.UrlError, e:
    logging.warn("Url added by: %s had problem.\n Error was: %s" % (nickname, e))
    return
  hub = parser.extractHub()
  sourceUrl = parser.extractSourceUrl()
  author = parser.extractFeedAuthor()

  # Store the url as a Feed
  subscription = Subscription(url=url, subscriber=nickname, hub=hub, sourceUrl=sourceUrl, author=author, key_name=url)
  subscription.put()

  # Tell the hub about the url
  hubSubscriber = pshb.HubSubscriber()
  hubSubscriber.subscribe(url, hub, "http://%s.appspot.com/posts" % settings.APP_NAME)

  # Store the current content of the feed
  posts = parser.extractPosts()
  logging.info("About to store %d new posts for subscription: %s" % (len(posts), url))
  db.put(posts)

class SubscriptionsHandler(BaseAdminHandler):
  def get(self):
    """Show all the resources in this collection"""
    # Render them in the template
    templateValues = getAllSubscriptionsAsTemplateValues()
    render(self.response.out, 'subscriptions.html', templateValues)

  def post(self):
    """Create a new resource in this collection"""
    # Only admins can add new subscriptions
    if not userIsAdmin():
      self.error(403)
      self.response.out.write("You are not the Admin")
      return

    # Extract the url from the request
    url = self.request.get('url')
    if not url or len(url.strip()) == 0:
      self.response.set_status(500)
      return

    self.addNewSubscription(url)

    # Redirect the user via a GET
    self.redirect('/subscriptions')

class PostsHandler(webapp.RequestHandler):
  def get(self):
    """Show all the resources in this collection"""
    # If this is a hub challenge
    if self.request.get('hub.challenge'):
      mode = self.request.get('hub.mode')
      topic = self.request.get('hub.topic')
      if mode == "subscribe" and Subscription.exists(topic):
        # If this is a subscription and the URL is one we have in our database
        self.response.out.write(self.request.get('hub.challenge'))
        logging.info("Successfully accepted challenge for subscription to feed: %s" % topic)
      elif mode == "unsubscribe" and not Subscription.exists(topic):
        # If this is an unsubscription then we shouldn't have the URL in our database since it should already have been
        # deleted.
        self.response.out.write(self.request.get('hub.challenge'))
        logging.info("Successfully accepted challenge for unsubscription to feed: %s" % topic)
      else:
        self.response.set_status(404)
        self.response.out.write("Challenge failed for feed: %s with mode: %s" % (topic, mode))
        logging.info("Challenge failed for feed: %s with mode: %s" % (topic, mode))
      # Once a challenge has been issued there's no point in returning anything other than challenge passed or failed
      return

    # Get the last N posts ordered by date
    limit = 60
    posts = db.GqlQuery('SELECT * from Post ORDER by datePublished desc LIMIT %d' % limit)

    # Render them in the template
    templateValues = {'posts': posts}
    render(self.response.out, 'posts.html', templateValues)

  def post(self):
    """Create a new resource in this collection"""
    logging.info("New content: %s" % self.request.body)
    #TODO Extract out as much of this and move it into a deferred function
    parser = pshb.ContentParser(self.request.body, settings.DEFAULT_HUB, settings.ALWAYS_USE_DEFAULT_HUB)
    url = parser.extractFeedUrl()

    # This is a hack since the correct thing to do is to fetch the feed at subscription
    # time and store the self element inside the feed then use that for comparisons.
    if settings.SHOULD_VERIFY_INCOMING_POSTS:
      if not Subscription.exists(url):
      #404 chosen because the subscription doesn't exist
        self.response.set_status(404)
        self.response.out.write("We don't have a subscription for that feed: %s" % url)
        logging.warn("We don't have a subscription for that feed: %s" % url)
        return

    if not parser.dataValid():
      parser.logErrors()
      self.response.out.write("Bad entries: %s" % parser.data)
      return
    else:
      posts = parser.extractPosts()
      db.put(posts)
      logging.info("Successfully added posts")
      self.response.set_status(200)
      self.response.out.write("Good entries")


application = webapp.WSGIApplication([
                                         ('/', PostsHandler),
                                         ('/about', AboutHandler),
                                         ('/admin/addSubscription', AdminAddSubscriptionHandler),
                                         ('/admin/deleteSubscription', AdminDeleteSubscriptionHandler),
                                         ('/admin/refreshSubscriptions', AdminRefreshSubscriptionsHandler),
                                         ('/posts', PostsHandler),
                                         ('/subscriptions', SubscriptionsHandler),
                                         ('/bgtasks', BackGroundTaskHandler), ],
                                     debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
