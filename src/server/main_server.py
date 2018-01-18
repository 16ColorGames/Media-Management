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


def user_required(handler):
  """
    Decorator that checks if there's a user associated with the current session.
    Will also fail if there's no session present.
  """
  def check_login(self, *args, **kwargs):
    auth = self.auth
    if not auth.get_user_by_session():
      self.redirect(self.uri_for('login'), abort=True)
    else:
      return handler(self, *args, **kwargs)

  return check_login
  
  
def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text  # or whatever


    
class BaseHandler(webapp2.RequestHandler):
  @webapp2.cached_property
  def auth(self):
    """Shortcut to access the auth instance as a property."""
    return auth.get_auth()

  @webapp2.cached_property
  def user_info(self):
    """Shortcut to access a subset of the user attributes that are stored
    in the session.
    The list of attributes to store in the session is specified in
      config['webapp2_extras.auth']['user_attributes'].
    :returns
      A dictionary with most user information
    """
    return self.auth.get_user_by_session()

  @webapp2.cached_property
  def user(self):
    """Shortcut to access the current logged in user.
    Unlike user_info, it fetches information from the persistence layer and
    returns an instance of the underlying model.
    :returns
      The instance of the user model associated to the logged in user.
    """
    u = self.user_info
    return self.user_model.get_by_id(u['user_id']) if u else None

  @webapp2.cached_property
  def user_model(self):
    """Returns the implementation of the user model.
    It is consistent with config['webapp2_extras.auth']['user_model'], if set.
    """    
    return self.auth.store.user_model

  @webapp2.cached_property
  def session(self):
      """Shortcut to access the current session."""
      return self.session_store.get_session()

  def render_template(self, view_filename, params=None):    
    if not params:
        params = {}
    user = self.user_info
    params['user'] = user
    path = os.path.join(os.path.dirname(__file__), '../templates', view_filename)
    file = open(path, 'r')
    text = file.read()
    file.close()
    rtemplate = Environment(loader=FileSystemLoader('templates')).from_string(text)
    self.response.out.write(rtemplate.render( params))
    
  def display_message(self, message):
    """Utility function to display a template with a simple message."""
    params = {
      'content': message
    }
    render_template(self, 'simple.html', params)

  # this is needed for webapp2 sessions to work
  def dispatch(self):
      # Get a session store for this request.
      self.session_store = sessions.get_store(request=self.request)

      try:
          # Dispatch the request.
          webapp2.RequestHandler.dispatch(self)
      finally:
          # Save all sessions.
          self.session_store.save_sessions(self.response)
    
    
class SignupHandler(BaseHandler):
  def get(self):
    return render_template(self, 'signup.html')

  def post(self):
    user_name = self.request.get('username')
    email = self.request.get('email')
    name = self.request.get('name')
    password = self.request.get('password')
    last_name = self.request.get('lastname')

    unique_properties = ['email_address']
    user_data = self.user_model.create_user(user_name,
      unique_properties,
      email_address=email, name=name, password_raw=password,
      last_name=last_name, verified=False)
    if not user_data[0]: #user_data is a tuple
      self.display_message('Unable to create user for email %s because of \
        duplicate keys %s' % (user_name, user_data[1]))
      return
    
    user = user_data[1]
    user_id = user.get_id()

    token = self.user_model.create_signup_token(user_id)

    verification_url = self.uri_for('verification', type='v', user_id=user_id,
      signup_token=token, _full=True)

    msg = 'Send an email to user in order to verify their address. \
          They will be able to do so by visiting <a href="{url}">{url}</a>'

    self.display_message(msg.format(url=verification_url))
    
    
class MainPage(BaseHandler):
    def get(self):
        self.session_store = sessions.get_store(request=self.request)
        return render_template(self, 'home.html', {"title": "Media Management"})

        
class VerificationHandler(BaseHandler):
  def get(self, *args, **kwargs):
    user = None
    user_id = kwargs['user_id']
    signup_token = kwargs['signup_token']
    verification_type = kwargs['type']

    # it should be something more concise like
    # self.auth.get_user_by_token(user_id, signup_token)
    # unfortunately the auth interface does not (yet) allow to manipulate
    # signup tokens concisely
    user, ts = self.user_model.get_by_auth_token(int(user_id), signup_token,
      'signup')

    if not user:
      logging.info('Could not find any user with id "%s" signup token "%s"',
        user_id, signup_token)
      self.abort(404)
    
    # store user data in the session
    self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)

    if verification_type == 'v':
      # remove signup token, we don't want users to come back with an old link
      self.user_model.delete_signup_token(user.get_id(), signup_token)

      if not user.verified:
        user.verified = True
        user.put()

      self.display_message('User email address has been verified.')
      return
    elif verification_type == 'p':
      # supply user to the page
      params = {
        'user': user,
        'token': signup_token
      }
      return render_template(self, 'resetpassword.html', params)
    else:
      logging.info('verification type not supported')
      self.abort(404)
      
      
class LoginHandler(BaseHandler):
  def get(self):
    self._serve_page()

  def post(self):
    username = self.request.get('username')
    password = self.request.get('password')
    try:
      u = self.auth.get_user_by_password(username, password, remember=True,
        save_session=True)
      self.redirect(self.uri_for('home'))
    except (InvalidAuthIdError, InvalidPasswordError) as e:
      logging.info('Login failed for user %s because of %s', username, type(e))
      self._serve_page(True)

  def _serve_page(self, failed=False):
    username = self.request.get('username')
    params = {
      'username': username,
      'failed': failed
    }
    render_template(self, 'login.html', params)

    
class AuthenticatedHandler(BaseHandler):
  @user_required
  def get(self):
    self.render_template('authenticated.html')
    
      
class PodcastDisplay(BaseHandler):
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
        self.render_template('podlist.html', data)
        
        
class FeedDisplay(BaseHandler):
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
            self.render_template('error.html', data)


class PodcastDateAdded(BaseHandler):
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
        self.render_template('multi_episode_display.html', data)

        
class PodcastDatePublished(BaseHandler):
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
        self.render_template('multi_episode_display.html', data)


class LogoutHandler(BaseHandler):
  def get(self):
    self.auth.unset_session()
    self.redirect(self.uri_for('home'))
   
   
class ForgotPasswordHandler(BaseHandler):
  def get(self):
    self._serve_page()

  def post(self):
    username = self.request.get('username')

    user = self.user_model.get_by_auth_id(username)
    if not user:
      logging.info('Could not find any user entry for username %s', username)
      self._serve_page(not_found=True)
      return

    user_id = user.get_id()
    token = self.user_model.create_signup_token(user_id)

    verification_url = self.uri_for('verification', type='p', user_id=user_id,
      signup_token=token, _full=True)

    msg = 'Send an email to user in order to reset their password. \
          They will be able to do so by visiting <a href="{url}">{url}</a>'

    self.display_message(msg.format(url=verification_url))
  
  def _serve_page(self, not_found=False):
    username = self.request.get('username')
    params = {
      'username': username,
      'not_found': not_found
    }
    self.render_template('forgot.html', params)
    
    
routes = [
    webapp2.Route('/', MainPage, name='home'),
    ('/signup', SignupHandler),
    webapp2.Route('/login', LoginHandler, name='login'),
    ('/podcast', PodcastDisplay),
    webapp2.Route('/logout', LogoutHandler, name='logout'),
    webapp2.Route('/forgot', ForgotPasswordHandler, name='forgot'),
    ('/podcast/', PodcastDisplay),
    ('/podcast/feeds', PodcastDisplay),
    ('/podcast/feeds/', PodcastDisplay),
    ('/podcast/feed/(\d+)', FeedDisplay),
    webapp2.Route('/<type:v|p>/<user_id:\d+>-<signup_token:.+>',
      handler=VerificationHandler, name='verification'),
    ('/podcast/add/(\d\d\d\d-\d\d-\d\d)', PodcastDateAdded),
    ('/podcast/pub/(\d\d\d\d-\d\d-\d\d)', PodcastDatePublished),
    webapp2.Route('/authenticated', AuthenticatedHandler, name='authenticated')
    ]
config = {
    'webapp2_extras.auth': {
        'user_model': 'models.User',
        'user_attributes': ['name']
    },
    'webapp2_extras.sessions': {
        'secret_key': 'some_secret_key'
    }
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
