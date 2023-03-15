import logging
import socket
import subprocess
import time
from getpass import getpass
from pathlib import Path
from typing import Union

import invoke
import netifaces
import paramiko
from fabric import Connection, Config
from fabric import Result

logger = logging.getLogger('distributor')


def get_ip_addresses() -> list:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addresses = []
    for ifname in [y for x, y in socket.if_nameindex()]:
        try:
            ip = netifaces.ifaddresses(ifname)[netifaces.AF_INET][0]['addr']
        except KeyError:
            ip = None
        addresses.append(ip)
    return addresses


class NebulaSSH:
    def __init__(self, host: str, username: str, port: int = 22, known_hosts_file: Union[str, Path] = None, timeout: int = 3, sudo_password: str = None, retries: int = 20):
        self.host = host
        self.port = port
        self.username = username
        self.conn = None
        self.timeout = timeout
        self.channel = None
        self.sudo_password = None
        self.config = Config()
        self.retries = retries  # How many times we retry a command. Sometimes a sudo command failes for no reason.

        if sudo_password:
            self.set_sudo_password(sudo_password)

        # if known_hosts_file and not Path(known_hosts_file).is_file():
        #     raise FileNotFoundError
        # else:
        #     self.known_hosts_file = known_hosts_file

    def set_sudo_password(self, passwd: str = None):
        if passwd:
            self.sudo_password = passwd
        else:
            self.sudo_password = getpass(f'[sudo] password for {self.username}: ')
        self.config = Config(overrides={'sudo': {'password': self.sudo_password}})

    def connect(self, fail_soft: bool = False, print_err: bool = False) -> Union[Connection, None]:
        def do():
            for i in range(self.timeout):
                self.conn = Connection(host=self.host, user=self.username, port=self.port, config=self.config)
                try:
                    self.conn.open()
                except paramiko.ssh_exception.AuthenticationException:
                    self.copy_keys()
                    continue
                if self.conn.is_connected:
                    return self.conn
                elif print_err:
                    print('Failed to connect, retrying...')

        return do()

    # if fail_soft:
    #     try:
    #         return do()
    #     except paramiko.ssh_exception.AuthenticationException:
    #         return None
    # else:
    #     return do()

    # def ask_password(self, fail_soft: bool = False) -> Union[Connection, None]:
    #     for i in range(self.timeout):
    #         self.conn = self.connect(fail_soft=True)
    #         if self.conn:
    #             return self.conn
    #         else:
    #             print('Please log into', self.host)
    #             self.copy_keys()
    #             if self.conn is not None:
    #                 return self.conn
    #     if not fail_soft:
    #         raise ConnectionError(f'Failed to connect to {self.username}@{self.host}')

    def copy_keys(self):
        cmd = f'/usr/bin/ssh-copy-id -p {self.port} {self.username}@{self.host}'
        subprocess.run(cmd, shell=True)
        # os.system(cmd)

    def execute(self, cmd: str, sudo=False, print_err: bool = False) -> Union[Result, None]:
        if sudo:
            exe = self.conn.sudo
        else:
            exe = self.conn.run
        failed = False
        for i in range(self.retries):
            try:
                if failed and print_err:
                    print('\n\nEncountered error.')
                    print(f'Retry {i}/{self.retries}...\nSleeping 2s...')
                    time.sleep(2)
                    if not i % 5:
                        print('Reconnecting every 5 failures...')
                        self.close()
                        del self.conn
                        self.connect()
                        print('Connected!\nSleeping 10s...')
                        time.sleep(10)
                failed = False
                x = exe(cmd, hide=True)
                x.stdout = x.stdout.strip()
                return x
            except invoke.exceptions.UnexpectedExit as e:
                if print_err:
                    print(e)
                failed = True
                time.sleep(2)
            except paramiko.ssh_exception.AuthenticationException as e:
                print('Authentication failure:', e)
                self.copy_keys()
                failed = True

    # def check_connected(self) -> bool:
    # try:
    #     transport = self.conn.get_transport()
    #     transport.send_ignore()
    #     return True
    # except EOFError as e:
    #     return False
    # except KeyError as e:
    #     return False

    def close(self):
        self.conn.close()

    def check_host_up(self):
        try:
            socket.setdefaulttimeout(self.timeout)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, self.port))
        except OSError as e:
            return False
        else:
            s.close()
            return True

    # def execute_chain(self, chain_of_commands: Union[list, tuple], sudo: bool = False) -> List[Result]:
    #     outputs = []
    #     for cmd in chain_of_commands:
    #         x = self.execute(cmd, sudo=sudo)
    #         outputs.append(x)
    #     return outputs
    def sudo(self, cmd, print_err: bool = False) -> Result:
        return self.execute(cmd, sudo=True, print_err=print_err)
