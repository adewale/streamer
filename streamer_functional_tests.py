import os
import unittest

from gaetestbed import FunctionalTestCase
from google.appengine.ext import webapp

import streamer
import base64

# Set the environment so that tests which require admin privileges, and thus look up the user's email address, will pass
# See: http://code.google.com/p/nose-gae/issues/detail?id=13 for more
os.environ['AUTH_DOMAIN'] = 'example.org'
os.environ['USER_EMAIL'] = 'example@example.org'
os.environ['USER_ID'] = 'example' # Our test user is logged in
streamer.OPEN_ACCESS = True #Make the Admin pages visible to all


class SubscriptionsHandlerTest(FunctionalTestCase, unittest.TestCase):
	APPLICATION = streamer.application
	def assertOKAfterRedirect(self, response, expectedString=None):
		# Response should be a redirect that takes the user to a sensible page
		self.assertRedirects(response)
		response = response.follow()
		self.assertOK(response)
		if expectedString:
			response.mustcontain(expectedString)
		
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
		self.assertEqual(streamer.Subscription.all().count(), 1)

	def printTasks(self):
		tasks = []
		stub = self.get_task_queue_stub()
		
		for queue_name in self.get_task_queue_names():
			tasks.extend(stub.GetTasks(queue_name))
				
		for task in tasks:
			print task
		for task in tasks:
			params = {}
			decoded_body = base64.b64decode(task['body'])
            
			if decoded_body:
				# urlparse.parse_qs doesn't seem to be in Python 2.5...
				print "Decoded body:", decoded_body
				parts = [item.split('=', 2) for item in decoded_body.split('&')]
				print "Parts:", parts, len(parts)
				params = dict(parts)
            
				task.update({
					'decoded_body': decoded_body,
					'params': params,
					})
            

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

class AboutHandlerTest(FunctionalTestCase, unittest.TestCase):
	APPLICATION = streamer.application
	def testCanShowAboutPage(self):
		response = self.get('/about')
		self.assertOK(response)
		response.mustcontain("<title>About</title>")

class AdminHandlerTest(FunctionalTestCase, unittest.TestCase):
	APPLICATION = streamer.application
	def testCanShowAdminPage(self):
		response = self.get('/admin')
		self.assertOK(response)
		response.mustcontain("<title>Admin</title>")

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

class ContentParserFunctionalTest(unittest.TestCase):
	def testCanExtractPostsFromRemoteSite(self):
		parser = streamer.ContentParser(None, urlToFetch = "http://blog.oshineye.com/feeds/posts/default")
		posts = parser.extractPosts();
		self.assertTrue(len(posts) > 2 )
