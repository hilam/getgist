# coding: utf-8

import argparse
import json
import os

try:
    from urllib2 import HTTPError, Request, urlopen
    input = raw_input
except ImportError:
    from urllib.request import HTTPError, Request, urlopen


class Gist(object):

    api_url = 'https://api.github.com'

    def __init__(self, user=False, file_name=False, assume_yes=False):
        self.auth = None
        self.config(user, file_name, assume_yes)
        self.info = self.load_gist_info()

    def config(self, user, file_name, assume_yes):
        """
        Set the main variables used by GetGist instance
        :param user: (string) GitHub user name
        :param file_name: (string) Gist/file name to search for
        :param assume_yes: assume yes/default for all possible prompts
        :returns: None (it only set instance variables)
        """

        # set main variables
        self.user = user
        self.file_name = file_name
        self.assume_yes = assume_yes

        # load arguments
        if not self.user or not self.file_name:

            # set argparse
            parser = argparse.ArgumentParser()
            if not self.user:
                parser.add_argument('user', help='Gist username')
            if not self.file_name:
                parser.add_argument('file_name', help='Gist file name')
            parser.add_argument('-y', '--yes-to-all',
                                help='Assume `yes` to all prompts',
                                action="store_true")

            # load values from argparse
            args = parser.parse_args()
            if not user:
                self.user = args.user
            if not file_name:
                self.file_name = args.file_name
            if not assume_yes:
                self.assume_yes = args.yes_to_all

        # check if user is authenticated
        self.auth = self.authenticated()

        # set support variables
        self.local_dir = os.path.realpath(os.curdir)
        self.local_path = os.path.join(self.local_dir, self.file_name)

    @property
    def id(self):
        if self.info:
            return self.info.get('id', None)
        return False

    @property
    def raw_url(self):
        if self.info:
            return self.info.get('raw_url', None)
        return False

    def save(self):
        """Saves the contents of a gist to a file"""

        # check if file exists
        if os.path.exists(self.local_path):

            # delete or backup existing file?
            confirm = 'y'
            if not self.assume_yes:
                message = 'Delete existing {} ? (y/n) '
                confirm = self.ask(message.format(self.file_name))

            # delete exitsing file
            if confirm.lower() == 'y':
                self.output('Deleting existing {} …'.format(self.file_name))
                os.remove(self.local_path)

            # backup existing file
            else:
                self.backup()

        # save new file
        with open(self.local_path, 'w') as file_handler:
            contents = self.curl(self.raw_url)
            self.output('Saving new {} …'.format(self.file_name))
            file_handler.write(contents)
        self.output('Saved as {}'.format(os.path.abspath(self.local_path)))
        self.output('Done!')

    def backup(self):
        """Locally backups the file that has the same name as the gist file"""
        count = 0
        name = '{}.bkp'.format(self.file_name)
        backup = os.path.join(self.local_dir, name)
        while os.path.exists(backup):
            count += 1
            name = '{}.bkp{}'.format(self.file_name, count)
            backup = os.path.join(self.local_dir, name)
        self.output('Moving existing {} to {}…'.format(self.file_name, name))
        os.rename(os.path.join(self.local_dir, self.file_name), backup)

    def authenticated(self):
        """Check if access token is set and valid (boolean)"""
        self.token = self.get_token()
        valid = self.validate_token()
        if not self.token or not valid:
            self.output('Looking for public Gists only.')
            return False
        self.output('User `{}` authenticated.'.format(self.user))
        return True

    def get_token(self):
        """Loads and returns personal access token from env. variable"""
        token = os.getenv('GETGIST_TOKEN')
        if not token:
            self.output('No access token set.')
        return token

    def validate_token(self):
        """Reach API with access token (boolean)"""

        # if no token, return False
        if not self.token:
            return False

        # reach API
        headers = {'Authorization': 'token {}'.format(self.token)}
        url = '{}/user'.format(self.api_url)
        response = json.loads(self.curl(url, headers))

        # validate
        if response.get('login') != self.user:
            self.output('Invalid token for user {}.'.format(self.user))
            return False
        return True

    def load_gist_info(self):
        """
        Look for gists with the selected file name and return the gist's info
        :returns: (dict) containing the gist ID (id), description (description)
        and raw url (raw_url)
        """

        # return Gist info if Gist is found
        gists = [gist for gist in self.filter_gists()]
        if gists:
            return self.select_file(gists)

        # return False if no match if found
        error = "[Error] No file named `{}` found in {}'s Gists."
        self.output(error.format(self.file_name, self.user))
        return False

    def filter_gists(self):
        """
        Queries GitHub API searching for gists that have matching file names
        :returns: (list generator) list of dictiocnaries with matching gists
        """
        for gist in self.query_api():
            if self.file_name in gist['files']:
                yield {'id': gist['id'],
                       'description': gist['description'],
                       'raw_url': gist['files'][self.file_name]['raw_url']}

    def query_api(self):
        """
        Queries GitHub API looking for all gists of a given user
        :returns: (dict) dictionary converted version of the JSON response
        """
        url = '{}/users/{}/gists'.format(self.api_url, self.user)
        contents = str(self.curl(url))
        if not contents:
            self.output('[Hint] Check if the entered user name is correct.')
            return dict()
        return json.loads(contents)

    def select_file(self, files):
        """
        Given a list of matching files, returns the proper one
        :param files: (list) list of matching gists (as dictionaries)
        :returns: (dict) containing the gist ID (id), description (description)
        and raw url (raw_url)
        """

        # return false if no match
        if len(files) == 0:
            return False

        # if there is only one match (or `yes to all`), return the 1st match
        elif len(files) == 1 or self.assume_yes:
            return files[0]

        # if we have more macthes return the appropriate one
        else:

            # list and ask
            question = 'Download {} from which Gist?'.format(self.file_name)
            self.output(question)
            options = '[{}] {}'
            valid_indexes = list()
            for f in files:
                index = files.index(f)
                valid_indexes.append(index)
                self.output(options.format(index + 1, f['description']))

            # get the gist index
            try:
                gist_index = int(self.ask('Type the number: ')) - 1
            except:
                self.output('Please type a number.')
                return self.select_file(files)

            # check if entered index is valid
            if gist_index not in valid_indexes:
                self.output('Invalid number, please try again.')
                return self.select_file(files)

            # return the approproate file
            selected = files[gist_index]
            self.output('Using `{}` Gist…'.format(selected['description']))
            return selected

    def curl(self, url, headers=dict()):
        """
        Mimics the curl command
        :param url: (string) the URL to be read
        :returns: (string) the contents of the given URL
        """

        # include headers if authenticated
        if self.auth and 'Authorization' not in headers:
            headers['Authorization'] = 'token {}'.format(self.token)

        # try to connect
        self.output('Fetching {} …'.format(url))
        try:
            request = Request(url)
            for key in headers.keys():
                request.add_header(key, headers[key])
            response = urlopen(request)
            status = response.getcode()
        except HTTPError:
            self.output("[Error] Couldn't reach GitHub at {}.".format(url))
            return ''

        # if it works
        if status == 200:
            contents = response.read()
            return contents.decode('utf-8')

        # in case of error
        self.output('[Error] HTTP Status {}.'.format(url, status))
        return ''

    def indent(self, message, spaces=2):
        """A helper to indent output/input messages"""
        return '{}{}'.format(' ' * spaces, message)

    def output(self, message):
        """A helper to indent print()"""
        print(self.indent(message))

    def ask(self, message):
        """A helper to indent input()"""
        return input(self.indent(message))


class MyGist(Gist):

    def __init__(self, file_name=False, assume_yes=False):
        user = self.get_user()
        self.auth = None
        self.config(user, file_name, assume_yes)
        self.info = self.load_gist_info()

    def get_user(self):
        """For MyGist shortcut sets the proper GitHub user from env. var."""
        user = os.getenv('GETGIST_USER')
        if not user:
            self.output('No default user set yet. To avoid this prompt set an')
            self.output('environmental variable called `GETGIST_USER`.')
            user = self.ask('Please type your GitHub user name: ')
        return user


def run_getgist():
    gist = Gist()
    if gist.info:
        gist.save()


def run_getmy():
    gist = MyGist()
    if gist.info:
        gist.save()
