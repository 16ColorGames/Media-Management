import server_config

from jinja2 import Template
from jinja2 import Environment, FileSystemLoader

import logging
import os.path
import webapp2

from webapp2_extras import auth
from webapp2_extras import sessions

from webapp2_extras.auth import InvalidAuthIdError
from webapp2_extras.auth import InvalidPasswordError


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.session_store = sessions.get_store(request=self.request)
        return render_template(self, 'home.html')
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

routes = [('/', MainPage)]
config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'some_secret_key'
}
app = webapp2.WSGIApplication(routes, debug=True, config=config)

def start():
    print("Starting Server")
    from paste import httpserver
    httpserver.serve(app, host=server_config.host, port=server_config.port)
