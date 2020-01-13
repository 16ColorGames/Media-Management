import pymongo
from webapp2_extras import auth
from webapp2_extras import security

import server_config


class User(object):
    def __init__(self, id, username, friendly, level):
        self.id = id
        self.name = friendly
        self.username = username
        self.friendly = friendly
        self.level = level

    def get_level(self):
        """Returns this users access level"""
        return self.level

    def get_id(self):
        """Returns this user's unique ID, which can be an integer or string."""
        return self.id

    @classmethod
    def get_by_auth_token(cls, user_id, token):
        """Returns a user object based on a user ID and token.

        :param user_id:
            The user_id of the requesting user.
        :param token:
            The token string to be verified.
        :returns:
            A tuple ``(User, timestamp)``, with a user object and
            the token timestamp, or ``(None, None)`` if both were not found.
        """
        return None, None

    @classmethod
    def get_by_auth_password(cls, auth_id, password):
        """Returns a user object, validating password.

        :param auth_id:
            Authentication id. In this application, the email
        :param password:
            Password to be checked.
        :returns:
            A user object, if found and password matches.
        :raises:
            ``auth.InvalidAuthIdError`` or ``auth.InvalidPasswordError``.
        """
        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["users"]

        user_result = mycol.find_one({"email": auth_id})

        if user_result is None:
            raise auth.InvalidAuthIdError()

        if not security.check_password_hash(password, user_result['password']):
            raise auth.InvalidPasswordError()

        return User(user_result['user_id'], auth_id, user_result['friendly_name'], user_result['level'])

    @classmethod
    def create_auth_token(cls, user_id):
        """Creates a new authorization token for a given user ID.

        :param user_id:
            User unique ID.
        :returns:
            A string with the authorization token.
        """

    @classmethod
    def delete_auth_token(cls, user_id, token):
        """Deletes a given authorization token.

        :param user_id:
            User unique ID.
        :param token:
            A string with the authorization token.
        """

    @classmethod
    def create_user(cls, **user_values):
        """Creates a new user.

        :param auth_id:
            A string that is unique to the user. Users may have multiple
            auth ids. Example auth ids:

            - own:username
            - own:email@example.com
            - google:username
            - yahoo:username

            The value of `auth_id` must be unique.
        :param unique_properties:
            Sequence of extra property names that must be unique.
        :param user_values:
            Keyword arguments to create a new user entity. Since the model is
            an ``Expando``, any provided custom properties will be saved.
            To hash a plain password, pass a keyword ``password_raw``.
        :returns:
            A tuple (boolean, info). The boolean indicates if the user
            was created. If creation succeeds, ``info`` is the verification code;
            otherwise it is a list of duplicated unique properties that
            caused creation to fail.
        """

        if 'password_raw' in user_values:
            user_values['password'] = security.generate_password_hash(
                user_values.pop('password_raw'), length=12)

        myclient = pymongo.MongoClient(server_config.mongodbURL)
        mydb = myclient[server_config.mongodbDB]
        mycol = mydb["users"]

        user_result = mycol.find_one({"email": user_values['email_address']})

        if user_result is None:
            verify = security.generate_random_string(length=12,
                                                     pool='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
            user_dict = {"user_id": None, "password": user_values['password'], "email": user_values['email_address'],
                         "activation_key": verify, "friendly_name": user_values['friendly'], "level": 5}
            mycol.insert_one(user_dict)
            return True, verify
        else:
            return False, "Email"
