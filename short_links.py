import os
import urllib
import base64
import random

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

NUM_SHARDS = 20


class SimpleCounterShard(ndb.Model):
    """Shards for the counter"""
    count = ndb.IntegerProperty(default=0)


def get_count():
    """Retrieve the value for a given sharded counter.

    Returns:
        Integer; the cumulative count of all sharded counters.
    """
    total = 0
    for counter in SimpleCounterShard.query():
        total += counter.count
    return total


@ndb.transactional
def increment():
    """Increment the value for a given sharded counter."""
    shard_string_index = str(random.randint(0, NUM_SHARDS - 1))
    counter = SimpleCounterShard.get_by_id(shard_string_index)
    if counter is None:
        counter = SimpleCounterShard(id=shard_string_index)
    counter.count += 1
    counter.put()


class Link(ndb.Model):
    full_link = ndb.StringProperty(indexed=False)
    short_link = ndb.StringProperty()
    user = ndb.UserProperty()


class IndexPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        links = ''
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            links_query = Link.query(Link.user == user)
            links = links_query.fetch(10)
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'links': links,
            'user': user,
            'url': url,
            'url_linktext': url_linktext,
            'request': self.request.application_url+'/',
            'message': self.request.get('message')
        }
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))


class NewLink(webapp2.RequestHandler):
    def post(self):
        # Check if url is correct
        try:
            urllib.urlopen(self.request.get('full_link'))
        except IOError:
            return self.redirect('/?'+urllib.urlencode({'message':'Oops, You entered wrong url!'}))

        user = users.get_current_user()
        if user:
            link = Link(user=user, full_link=self.request.get('link'))
        else:
            link = Link(full_link=self.request.get('link'))

        link.full_link = self.request.get('full_link')
        link.short_link = base64.urlsafe_b64encode(str(get_count()))
        link.put()
        increment()
        # import pdb; pdb.set_trace()
        template_values = {
            'link': link,
            'user': user,
            'request': self.request.application_url+'/'
        }
        template = JINJA_ENVIRONMENT.get_template('new_link.html')
        self.response.write(template.render(template_values))


class ShortLink(webapp2.RequestHandler):
    def get(self, short_link):
        links_query = Link.query(Link.short_link == short_link)
        link = links_query.get()
        if link:
            self.redirect(str(link.full_link))
        else:
            self.redirect('/')


application = webapp2.WSGIApplication([
                                          ('/', IndexPage),
                                          ('/create', NewLink),
                                          webapp2.Route(r'/<short_link:[^/]+>', handler=ShortLink, name='short_link'),
                                      ], debug=True)