from getpass import getpass
from typing import Union

import keyring


class Passwords:
    auth = {}
    service_id = 'nebula-network-distributor'

    def __init__(self):
        pass

    def set(self, username, password):
        self.auth[username] = password
        keyring.set_password(self.service_id, username, password)

    def prompt(self, username):
        pw = getpass(f'[sudo] password for {username}: ')
        self.set(username, pw)

    def get(self, username) -> Union[str, None]:
        if username not in self.auth:
            return keyring.get_password(self.service_id, username)
        else:
            return self.auth[username]
