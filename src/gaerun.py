# GAE-RUN - Makes running Google App Engine code easy.
# 
# Author: Luke Hubbard - http://twitter.com/lukeinth
# 
# Usage: 
#  - Make sure you have Google App Engine installed. 
#  - Download this file and save as gaerun.py in your app folder.
#  - Add "import gaerun" at the t
# op of your code.
#  - Run your code using command line / editor. Tip: (command + R) in textmate
# 
# Example:
# 
# import gaerun
# if __name__ == "__main__": 
#     from google.appengine.api import memcache
#     memcache.set('greeting','hello world')
#     print memcache.get('greeting')

import logging, os, sys

APP_PATH = os.path.dirname(__file__)

def load_sdk():
    
    # Code from: http://google-app-engine-django.googlecode.com/svn/trunk/appengine_django/__init__.py
    # Updates: Added GAE_HOME as first choice.
    # Try to import the appengine code from the system path.
    try:
        from google.appengine.api import apiproxy_stub_map
    except ImportError, e:
        # Hack to fix reports of import errors on Ubuntu 9.10.
        if 'google' in sys.modules:
            del sys.modules['google']
        # Not on the system path. Build a list of alternative paths where it may be.
        # First look within the project for a local copy, then look for where the Mac
        # OS SDK installs it.
        paths = [os.environ.get('GAE_HOME', ''),
                 os.path.join(APP_PATH, '.google_appengine'),
                 os.path.join(APP_PATH, 'google_appengine'),
                 '/usr/local/google_appengine']
                 
        # Then if on windows, look for where the Windows SDK installed it.
        for path in os.environ.get('PATH', '').split(';'):
            path = path.rstrip('\\')
            if path.endswith('google_appengine'):
                paths.append(path)
        try:
            from win32com.shell import shell
            from win32com.shell import shellcon
            id_list = shell.SHGetSpecialFolderLocation(
                    0, shellcon.CSIDL_PROGRAM_FILES)
            program_files = shell.SHGetPathFromIDList(id_list)
            paths.append(os.path.join(program_files, 'Google',
                                                                'google_appengine'))
        except ImportError, e:
            # Not windows.
            pass
            
        # Loop through all possible paths and look for the SDK dir.
        SDK_PATH = None
        for sdk_path in paths:
            if os.path.exists(sdk_path):
                SDK_PATH = os.path.realpath(sdk_path)
                break
        if SDK_PATH is None:
            # The SDK could not be found in any known location.
            sys.stderr.write("The Google App Engine SDK could not be found!\n")
            sys.stderr.write("See README for installation instructions.\n")
            sys.exit(1)
        if SDK_PATH == os.path.join(APP_PATH, 'google_appengine'):
            logging.warn('Loading the SDK from the \'google_appengine\' subdirectory '
                                     'is now deprecated!')
            logging.warn('Please move the SDK to a subdirectory named '
                                     '\'.google_appengine\' instead.')
            logging.warn('See README for further details.')
        # Add the SDK and the libraries within it to the system path.
        EXTRA_PATHS = [
                SDK_PATH,
                os.path.join(SDK_PATH, 'lib', 'antlr3'),
                os.path.join(SDK_PATH, 'lib', 'django'),
                os.path.join(SDK_PATH, 'lib', 'webob'),
                os.path.join(SDK_PATH, 'lib', 'yaml', 'lib'),
        ]
        
        lib_dir = os.path.join(APP_PATH, 'lib')
        if os.path.exists(lib_dir):
            EXTRA_PATHS.append(lib_dir)
        
        # Add SDK paths at the start of sys.path, but after the local directory which
        # was added to the start of sys.path on line 50 above. The local directory
        # must come first to allow the local imports to override the SDK and
        # site-packages directories.
        sys.path = sys.path[0:1] + EXTRA_PATHS + sys.path[1:]
        
        
        
def setup_app_env():
    
    app_yaml = os.path.join(APP_PATH,'app.yaml')
    auth_domain = 'gmail.com'
    app_id = 'media-management-192515'
    if os.path.exists(app_yaml):
        import yaml
        f = open(app_yaml)
        app_settings = yaml.load(f)
        f.close()
        application = app_settings.get('application', None)
        if application:
            app_id = application
            logged_in_user = "%s@%s" % (application, auth_domain)
    else:
        logging.warn("Could not find app.yaml. Will fake it!")
    os.environ['AUTH_DOMAIN'] = auth_domain
    os.environ['APPLICATION_ID'] = app_id
    os.environ['APP_ID'] = app_id
    
def register_stubs():
    
    from google.appengine.api import apiproxy_stub_map
    from google.appengine.api import datastore_file_stub    
    from google.appengine.api import mail_stub
    from google.appengine.api import urlfetch_stub
    from google.appengine.api import user_service_stub
    from google.appengine.api.labs.taskqueue import taskqueue_stub
    from google.appengine.api.memcache import memcache_stub
 
    # Start with a fresh api proxy.
    apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
 
    # Use a fresh stub datastore.
    stub = datastore_file_stub.DatastoreFileStub(os.environ['APP_ID'], '/dev/null', '/dev/null')
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', stub)

    apiproxy_stub_map.apiproxy.RegisterStub(
        'taskqueue',
        taskqueue_stub.TaskQueueServiceStub())
 
    # Use a fresh stub UserService.
    apiproxy_stub_map.apiproxy.RegisterStub('user',
    user_service_stub.UserServiceStub())
    
    # Use a fresh urlfetch stub.
    apiproxy_stub_map.apiproxy.RegisterStub(
        'urlfetch', urlfetch_stub.URLFetchServiceStub())

    # Use a fresh mail stub.
    apiproxy_stub_map.apiproxy.RegisterStub(
        'mail', mail_stub.MailServiceStub(
                                       host='127.0.0.1',
                                       port=25,
                                       user='',
                                       password='',
                                       enable_sendmail=False,
                                       show_mail_body=True
                                    ))
  
    apiproxy_stub_map.apiproxy.RegisterStub(
        'memcache', memcache_stub.MemcacheServiceStub())
    
    try:
        from google.appengine.api.images import images_stub
        apiproxy_stub_map.apiproxy.RegisterStub(
            'images', images_stub.ImagesServiceStub())
    except ImportError, e:
        logging.warn("Unable to load images API, please check PIL is installed correctly!")

        
def wrap_except(code_which_might_except):
    
    import sys
    try:
        return code_which_might_except()
    except:
        return sys.exc_info()[1]

        
def startup():
    load_sdk()
    setup_app_env()
    register_stubs()
    logging.info("GAE-RUN v0.2 - Latest version: http://bit.ly/92N1Cw")
