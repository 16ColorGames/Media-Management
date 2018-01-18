import server_config

from jinja2 import Template
from jinja2 import Environment, FileSystemLoader

import logging
import os.path
import webapp2
import mysql.connector

from webapp2_extras import auth
from webapp2_extras import sessions

from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError

from paste import httpserver
from paste.urlparser import StaticURLParser
from paste.cascade import Cascade

from slugify import slugify

from datetime import datetime, date, timedelta
from google.appengine.api import users

def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text  # or whatever


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.session_store = sessions.get_store(request=self.request)
        return render_template(self, 'home.html', {"title": "Media Management"})
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

        
class PodcastDisplay(webapp2.RequestHandler):
    def get(self):
        self.session_store = sessions.get_store(request=self.request)
        # Connect with the MySQL Server
        cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
       
        feed_cursor = cnx.cursor(dictionary=True)
        feed_query = "SELECT * FROM podcast_feeds" # select all of our feeds
        feed_cursor.execute(feed_query)
        data = {"title": "Podcast Feeds"}
        feeds = []
        images = []
        for row in feed_cursor:
            row["slug"] = "/images/" + slugify(row['name'])
            feeds.append(row)
        data["feeds"] = feeds
        data["description"] = "<a href='/podcast/add/" + date.today().strftime('%Y-%m-%d') + "'>Podcasts added to the database today</a>"
        return render_template(self, 'podlist.html', data)
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()
        
        
class FeedDisplay(webapp2.RequestHandler):
    def get(self, feed_id):
        self.session_store = sessions.get_store(request=self.request)
        # Connect with the MySQL Server
        cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
       
        feed_cursor = cnx.cursor(dictionary=True)
        feed_query = "SELECT * FROM podcast_feeds WHERE feed_id = " + feed_id  # select our feed
        feed_cursor.execute(feed_query)
        
        data = {}
        row = feed_cursor.fetchone()
        if row is not None:
            data["title"] = row["name"]
            data["description"] = row["description"]
            episode_cursor = cnx.cursor(dictionary=True)
            episode_query = "SELECT * FROM podcast_episodes WHERE feed = " + feed_id + " ORDER BY pubDate"
            episode_cursor.execute(episode_query)
            episodes = []
            for eprow in episode_cursor:
                eprow['file'] = remove_prefix(eprow['file'], server_config.podcast_directory)
                episodes.append(eprow)
            data["image"] = "/images/" + slugify(row['name'])
            data["episodes"] = episodes
            return render_template(self, 'podfeed.html', data)
        else:
            data["title"] = "Error: Feed not found"
            data["error"] = "There was an issue while retrieving the feed data. The feed probably wasn't added to the database properly. " + feed_query
            return render_template(self, 'error.html', data)
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()


class PodcastDateAdded(webapp2.RequestHandler):
    def get(self, day):
        self.session_store = sessions.get_store(request=self.request)
        # Connect with the MySQL Server
        cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
        
        theday = datetime.strptime(day, "%Y-%m-%d").date()
        
        prevday = theday - timedelta(days=1)
        prevdatestr = prevday.strftime('%Y-%m-%d')
        nextday = theday + timedelta(days=1)
        nextdatestr = nextday.strftime('%Y-%m-%d')
       
       
        feed_cursor = cnx.cursor(dictionary=True)
        feed_query = "SELECT * FROM podcast_episodes WHERE addDate BETWEEN '" + day + " 00:00:00' AND '" + day + " 23:59:59'"  # select our feed
        feed_cursor.execute(feed_query)
        episodes = []
        for row in feed_cursor:
            episodes.append(row)
        
        data = {}
        data["description"] = "<a href='" + prevdatestr + "'>Previous Day</a> Episodes added on " + day + " <a href='" + nextdatestr + "'>Next Day</a>"
        data["episodes"] = episodes
        data["title"] = "Episodes added on " + day
        return render_template(self, 'multi_episode_display.html', data)
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

        
class PodcastDatePublished(webapp2.RequestHandler):
    def get(self, day):
        self.session_store = sessions.get_store(request=self.request)
        # Connect with the MySQL Server
        cnx = mysql.connector.connect(user=server_config.mysqlUser, password=server_config.mysqlPassword, database=server_config.mysqlDatabase)
        
        theday = datetime.strptime(day, "%Y-%m-%d").date()
        
        prevday = theday - timedelta(days=1)
        prevdatestr = prevday.strftime('%Y-%m-%d')
        nextday = theday + timedelta(days=1)
        nextdatestr = nextday.strftime('%Y-%m-%d')
       
       
        feed_cursor = cnx.cursor(dictionary=True)
        feed_query = "SELECT * FROM podcast_episodes WHERE pubDate BETWEEN '" + day + " 00:00:00' AND '" + day + " 23:59:59'"  # select our feed
        feed_cursor.execute(feed_query)
        episodes = []
        for row in feed_cursor:
            episodes.append(row)
        
        data = {}
        data["description"] = "<a href='" + prevdatestr + "'>Previous Day</a> Episodes added on " + day + " <a href='" + nextdatestr + "'>Next Day</a>"
        data["episodes"] = episodes
        data["title"] = "Episodes published on " + day
        return render_template(self, 'multi_episode_display.html', data)
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

        
class SessionSet(webapp2.RequestHandler):
    def get(self, data):
        self.session_store = sessions.get_store(request=self.request)
        
        return render_template(self, 'simple.html', {"content": "Added Data to Session"})
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

        
def render_template(self, view_filename, params=None):
    if not params:
        params = {}
    path = os.path.join(os.path.dirname(__file__), '../templates', view_filename)
    file = open(path, 'r')
    text = file.read()
    file.close()
    rtemplate = Environment(loader=FileSystemLoader('templates')).from_string(text)
    self.response.out.write(rtemplate.render( params))

routes = [
    ('/', MainPage),
    ('/session/add/(.*)', SessionSet),
    ('/session/view', SessionView),
    ('/podcast', PodcastDisplay),
    ('/podcast/', PodcastDisplay),
    ('/podcast/feeds', PodcastDisplay),
    ('/podcast/feeds/', PodcastDisplay),
    ('/podcast/feed/(\d+)', FeedDisplay),
    ('/podcast/add/(\d\d\d\d-\d\d-\d\d)', PodcastDateAdded),
    ('/podcast/pub/(\d\d\d\d-\d\d-\d\d)', PodcastDatePublished)
    ]
config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'some_secret_key'
}
web_app = webapp2.WSGIApplication(routes, debug=True, config=config)

# Create an app to serve static files
# Choose a directory separate from your source (e.g., "./static/") so it isn't dl'able
static_app = StaticURLParser("./static")
podcast_app = StaticURLParser(server_config.podcast_directory)

app = Cascade([static_app, podcast_app, web_app])

def start():
    print("Starting Server")
    print(static_app)
    httpserver.serve(app, host=server_config.host, port=server_config.port)
