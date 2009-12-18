import os
import unittest

from webtest import TestApp
from google.appengine.ext import webapp

import streamer

APP = TestApp(streamer.application)

# Set the environment so that tests which require admin privileges, and thus look up the user's email address, will pass
# See: http://code.google.com/p/nose-gae/issues/detail?id=13 for more
os.environ['AUTH_DOMAIN'] = 'example.org'
os.environ['USER_EMAIL'] = 'example@example.org'
os.environ['USER_ID'] = 'example' # Our test user is logged in
streamer.OPEN_ACCESS = True #Make the Admin pages visible to all


class SubscriptionsHandlerTest(unittest.TestCase):
	def testCanShowSubscriptions(self):
		response = APP.get('/subscriptions')
		self.assertEquals('200 OK', response.status)
		response.mustcontain("<title>Subscriptions</title>")

class PostsHandlerTest(unittest.TestCase):
	def testCanShowPosts(self):
		response = APP.get('/posts')
		self.assertEquals('200 OK', response.status)
		response.mustcontain("<title>Posts</title>")
	
	def testGoingToSlashIsTheSameAsPostsPage(self):
		responseFromPostsPage = APP.get('/posts')
		responseFromSlash = APP.get('/')
		self.assertEquals(responseFromPostsPage.body, responseFromSlash.body)
		self.assertEquals(responseFromPostsPage.status, responseFromSlash.status)

class AboutHandlerTest(unittest.TestCase):
	def testCanShowAboutPage(self):
		response = APP.get('/about')
		self.assertEquals('200 OK', response.status)
		response.mustcontain("<title>About</title>")

class AdminHandlerTest(unittest.TestCase):
	def testCanShowAdminPage(self):
		response = APP.get('/admin')
		self.assertEquals('200 OK', response.status)
		response.mustcontain("<title>Admin</title>")

class AdminAddSubscriptionHandlerTest(unittest.TestCase):
	def testCanShowAddSubscriptionPage(self):
		response = APP.get('/admin/addSubscription')
		self.assertEquals('200 OK', response.status)
		response.mustcontain("<title>Add Subscription</title>")

class AdminDeleteSubscriptionHandlerTest(unittest.TestCase):
	def testCanShowDeleteSubscriptionPage(self):
		response = APP.get('/admin/deleteSubscription')
		self.assertEquals('200 OK', response.status)
		response.mustcontain("<title>Delete Subscription</title>")