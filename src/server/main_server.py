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
        for row in feed_cursor:
            feeds.append(row)
        data["feeds"] = feeds
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
                episodes.append(eprow)
            data["title"] = row['name']
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
    ('/podcast', PodcastDisplay),
    ('/podcast/(\d+)', FeedDisplay)
    ]
config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'some_secret_key'
}
web_app = webapp2.WSGIApplication(routes, debug=True, config=config)

# Create an app to serve static files
# Choose a directory separate from your source (e.g., "static/") so it isn't dl'able
static_app = StaticURLParser("./static")

app = Cascade([static_app, web_app])

def start():
    print("Starting Server")
    print(static_app)
    httpserver.serve(app, host=server_config.host, port=server_config.port)
