import logging
import os.path
from datetime import datetime, date, timedelta

import pymongo
import server_config
import webapp2
from bson import ObjectId
from jinja2 import Environment, FileSystemLoader
from paste import httpserver
from paste.cascade import Cascade
from paste.urlparser import StaticURLParser
from slugify import slugify
from webapp2_extras import auth
from webapp2_extras import sessions
from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError


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
        self.response.out.write(rtemplate.render(params))

    def display_message(self, message):
        """Utility function to display a template with a simple message."""
        params = {
            'content': message
        }
        self.render_template('simple.html', params)

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
        self.render_template('signup.html')

    def post(self):
        email = self.request.get('email')
        name = self.request.get('name')
        password = self.request.get('password')

        user_data = self.user_model.create_user(
            email_address=email, friendly=name, password_raw=password,
            verified=False)
        if not user_data[0]:  # user_data is a tuple
            self.display_message('Unable to create user for email %s because of \
        duplicate keys %s' % (email, user_data[1]))
            return

        verify = user_data[1]

        msg = 'Send an email to user in order to verify their address. \
          They will be able to do so by visiting <a href="{url}">{url}</a>'

        self.display_message(msg.format(url=verify))


class MainPage(BaseHandler):
    def get(self):
        self.session_store = sessions.get_store(request=self.request)
        self.render_template('home.html', {"title": "Media Management"})


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
            self.render_template('resetpassword.html', params)
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
        self.render_template('login.html', params)


class ApproveIDHandler(BaseHandler):
    def get(self):
        self._serve_page()

    @user_required
    def post(self, item_id):
        TMDBid = self.request.get('Correct Id')
        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        itemcol = mydb["items"]
        tagcol = mydb["tags"]
        recol = mydb["requests"]

        item = itemcol.find_one({"_id": ObjectId(str(item_id))})

        if item is not None:
            itemcol.delete_one({"_id": ObjectId(str(item_id))})
            try:
                item["Tags"].remove(tagcol.find_one({"Name": "Unprocessed", "Type": "Admin"}).get("_id"))
            except ValueError:
                pass
            item["Tags"].append(tagcol.find_one({"Name": "Approved", "Type": "Admin"}).get("_id"))
            item["TMDBid"] = TMDBid
            itemcol.insert_one(item)
            recol.insert_one({"Object": "Item", "Id": item.get("_id"), "Type": "Full"})
            recol.insert_one({"Object": "Item", "Id": item.get("_id"), "Type": "Cast"})

        self.display_message(item_id + ": " + TMDBid)

    def _serve_page(self, failed=False):
        username = self.request.get('username')
        params = {
            'username': username,
            'failed': failed
        }
        self.render_template('login.html', params)


class AuthenticatedHandler(BaseHandler):
    @user_required
    def get(self):
        self.render_template('authenticated.html')


class ApprovalDisplay(BaseHandler):
    @user_required
    def get(self):
        self.session_store = sessions.get_store(request=self.request)

        if self.auth.get_user_by_session()["level"] < 500:
            self.redirect(self.uri_for('login'), abort=True)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["items"]
        tagcol = mydb["tags"]
        data = {}
        tag_id = tagcol.find_one({"Type": "Admin", "Name": "Automatic"})["_id"];
        items = []
        for row in mycol.find({"Tags": tag_id}).sort([("Name", 1)]):
            items.append(row)
        data["items"] = items
        self.render_template('approval.html', data)


class PodcastDisplay(BaseHandler):
    def get(self):
        self.session_store = sessions.get_store(request=self.request)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["feeds"]

        data = {"title": "Podcast Feeds"}
        feeds = []
        images = []

        for row in mycol.find():
            row["slug"] = "/images/" + slugify(row['name'])
            row["_id"] = str(row['_id'])
            if "Patreon" in row["name"]:
                row["private"] = True
            else:
                row["private"] = False
            feeds.append(row)
        data["feeds"] = feeds
        data["description"] = "<a href='/podcast/add/" + date.today().strftime(
            '%Y-%m-%d') + "'>Podcasts added to the database today</a>"
        self.render_template('podlist.html', data)


class MasterFeedForward(BaseHandler):
    def get(self, xml):
        data = {}
        with open(server_config.podcast_directory + ".feeds/" + xml.lower(), 'r') as f:
            data['feed'] = f.read()
        self.render_template('xml_feed.html', data)
        
class FeedForward(BaseHandler):
    def get(self, xml):
        data = {}
        with open(server_config.podcast_directory + ".feeds/single/" + xml.lower() + ".xml", 'r') as f:
            data['feed'] = f.read()
        self.render_template('xml_feed.html', data)


class GenreDisplay(BaseHandler):
    @user_required
    def get(self):
        self.session_store = sessions.get_store(request=self.request)
        data = {"title": "Genres"}

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["tags"]

        genres = []

        for row in mycol.find({"Type": "Genre"}).sort([("Name", 1)]):
            row["_id"] = str(row['_id'])
            genres.append(row)

        data["genres"] = genres

        self.render_template('genres.html', data)


class TagListDisplay(BaseHandler):
    @user_required
    def get(self, tag_id):
        self.session_store = sessions.get_store(request=self.request)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["items"]
        tagcol = mydb["tags"]
        data = {}
        data["title"] = tagcol.find_one({"_id": ObjectId(str(tag_id))})["Name"];
        items = []
        for row in mycol.find({"Tags": ObjectId(str(tag_id))}).sort([("Name", 1)]):
            items.append(row)
        data["items"] = items
        self.render_template('tag_list.html', data);


class FeedDisplay(BaseHandler):
    def get(self, feed_id):
        self.session_store = sessions.get_store(request=self.request)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["feeds"]
        data = {}
        row = mycol.find_one({"_id": ObjectId(str(feed_id))})
        if row is not None:
            data["title"] = row["name"]
            data["description"] = row["description"]
            data["id"] = str(feed_id)

            epcol = mydb["episodes"]

            episodes = []
            for eprow in epcol.find({"feed": ObjectId(feed_id)}):
                eprow['file'] = remove_prefix(eprow['file'], server_config.podcast_directory)
                episodes.append(eprow)
            data["image"] = "/images/" + slugify(row['name'])
            data["episodes"] = episodes
            self.render_template('podfeed.html', data)
        else:
            data["title"] = "Error: Feed not found"
            data[
                "error"] = "There was an issue while retrieving the feed data. The feed probably wasn't added to the database properly."
            self.render_template('error.html', data)


class ItemDisplay(BaseHandler):
    def get(self, item_id):
        self.session_store = sessions.get_store(request=self.request)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["items"]
        entcol = mydb["entities"]
        relcol = mydb["relations"]

        row = mycol.find_one({"_id": ObjectId(str(item_id))})
        if row is not None:
            actors = []
            cast = relcol.find({"ItemId": row["_id"], "Relation": "Actor"})
            crew = relcol.find({"ItemId": row["_id"], "Relation": "Crew"})
            for c in cast:
                cm = entcol.find_one({"_id": c["EntityId"]})
                actors.append({"Name": cm["Name"], "id": cm["_id"], "Character": c["Character"]})
            row["actors"] = actors
            self.render_template('item.html', row)
        else:
            data = []
            data["title"] = "Error: Item not found"
            data["error"] = "There was an issue while retrieving the item data."
            self.render_template('error.html', data)


class EntityDisplay(BaseHandler):
    def get(self, item_id):
        self.session_store = sessions.get_store(request=self.request)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        itemcol = mydb["items"]
        entcol = mydb["entities"]
        relcol = mydb["relations"]

        row = entcol.find_one({"_id": ObjectId(str(item_id))})
        if row is not None:
            if row["Type"] == "Person":
                roles = []
                cast = relcol.find({"EntityId": row["_id"]})
                for c in cast:
                    cm = itemcol.find_one({"_id": c["ItemId"]})
                    roles.append({"Title": cm["Title"], "id": cm["_id"], "Character": c["Character"]})
                row["roles"] = roles
                self.render_template('person.html', row)
            else:
                data = []
                data["title"] = "Error: Type Not Handled"
                data["error"] = "This type of entity has not been handles by the server for public display."
                self.render_template('error.html', data)
        else:
            data=[]
            data["title"] = "Error: Entity not found"
            data["error"] = "There was an issue while retrieving the entity data."
            self.render_template('error.html', data)


class PodcastDateAdded(BaseHandler):
    def get(self, day):
        self.session_store = sessions.get_store(request=self.request)
        
        
        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["feeds"]
        by_id = {}
        for row in mycol.find():
            by_id[row['_id']] = row['name']

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        epcol = mydb["episodes"]

        theday = datetime.strptime(day, "%Y-%m-%d").date()

        prevday = theday - timedelta(days=1)
        prevdatestr = prevday.strftime('%Y-%m-%d')
        nextday = theday + timedelta(days=1)
        nextdatestr = nextday.strftime('%Y-%m-%d')

        data = {}
        episodes = []
        for eprow in epcol.find({'added': {'$lt': unicode(datetime.combine(theday, datetime.max.time())),
                                           '$gt': unicode(datetime.combine(theday, datetime.min.time()))}}):
            eprow['file'] = remove_prefix(eprow['file'], server_config.podcast_directory)
            eprow['feed_id'] = eprow['feed']
            eprow['feed_name'] = by_id[eprow['feed']]
            episodes.append(eprow)

        data[
            "description"] = "<a href='" + prevdatestr + "'>Previous Day</a> Episodes added on " + day + " <a href='" + nextdatestr + "'>Next Day</a>"
        data["episodes"] = episodes
        data["title"] = "Episodes added on " + day
        self.render_template('multi_episode_display.html', data)


class PodcastDatePublished(BaseHandler):
    def get(self, day):
        self.session_store = sessions.get_store(request=self.request)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        epcol = mydb["episodes"]

        theday = datetime.strptime(day, "%Y-%m-%d").date()

        prevday = theday - timedelta(days=1)
        prevdatestr = prevday.strftime('%Y-%m-%d')
        nextday = theday + timedelta(days=1)
        nextdatestr = nextday.strftime('%Y-%m-%d')

        data = {}
        episodes = []
        for eprow in epcol.find({'published': {'$lt': unicode(datetime.combine(theday, datetime.max.time())),
                                               '$gt': unicode(datetime.combine(theday, datetime.min.time()))}}):
            eprow['file'] = remove_prefix(eprow['file'], server_config.podcast_directory)
            eprow['feed_id'] = eprow['feed']
            episodes.append(eprow)

        data[
            "description"] = "<a href='" + prevdatestr + "'>Previous Day</a> Episodes Published on " + day + " <a href='" + nextdatestr + "'>Next Day</a>"
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
    ('/genres', GenreDisplay),
    ('/admin/approval', ApprovalDisplay),
    ('/podcast', PodcastDisplay),
    webapp2.Route('/logout', LogoutHandler, name='logout'),
    webapp2.Route('/forgot', ForgotPasswordHandler, name='forgot'),
    ('/podcast/', PodcastDisplay),
    ('/podcast/feeds', PodcastDisplay),
    ('/podcast/feeds/', PodcastDisplay),
    ('/podcast/masterfeeds/(.*\.xml$)', MasterFeedForward),
    ('/podcast/feed/(.*)/rss.xml', FeedForward),
    ('/podcast/feed/(.*)', FeedDisplay),
    ('/admin/approval/(.*)', ApproveIDHandler),
    ('/items/(.*)', ItemDisplay),
    ('/entities/(.*)', EntityDisplay),
    ('/tags/(.*)', TagListDisplay),
    webapp2.Route('/<type:v|p>/<user_id:\d+>-<signup_token:.+>',
                  handler=VerificationHandler, name='verification'),
    ('/podcast/add/(\d\d\d\d-\d\d-\d\d)', PodcastDateAdded),
    ('/podcast/pub/(\d\d\d\d-\d\d-\d\d)', PodcastDatePublished),
    webapp2.Route('/authenticated', AuthenticatedHandler, name='authenticated')
]
config = {
    'webapp2_extras.auth': {
        'user_model': 'models.User',
        'user_attributes': ['name', 'level']
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
images_app = StaticURLParser(server_config.storage_directory)

app = Cascade([static_app, podcast_app, web_app, images_app])


def start():
    print("Starting Server")
    print(static_app)
    httpserver.serve(app, host=server_config.host, port=server_config.port)
