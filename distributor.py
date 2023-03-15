#!/usr/bin/env python3
import argparse
import logging
import os
import shutil
import subprocess
import tempfile
import time
import traceback
import urllib.parse
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Union
from uuid import uuid4

import requests
import yaml

from nebula_distributor import HostBuilder, NebulaCerts, NebulaNetworkConfig, NebulaPaths, Passwords, create_installer_archive
from nebula_distributor.commands import install_cert, install_config, nebula_service_cmd
from nebula_distributor.ssh import NebulaSSH
from nebula_distributor.ssh import get_ip_addresses

script_directory = os.path.abspath(os.path.dirname(__file__))
config_to_ip = []
logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger('distributor')
yaml.Dumper.ignore_aliases = lambda *args: True  # Don't print pointers added when copying dicts

# TODO: get the latest release
nebula_latest = 'https://github.com/slackhq/nebula/releases/download/v1.6.1/'

parser = argparse.ArgumentParser(description='Nebula Network Distributor: an easy way to distribute configs and certs to your Nebula network.')
parser.add_argument('--config', default=Path(script_directory, 'config.yml'), help='Path to config.yml if it is not located next to this executable.')
parser.add_argument('--files', default=Path(script_directory, 'files'), help='Path to the nebula-files directory if it is not located next to this executable.')
parser.add_argument('--log', default=False, help='Log to this file.')
parser.add_argument('--restart-type', required=False, default='reload', choices=['reload', 'restart'], help='How to restart the Nebula service on the remote host.')
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--daemon', '-d', action='store_true', help='Start in daemon mode.')
parser.add_argument('--generate-certs', '-c', action='store_true', help='Generate and install new certs for each host.')
parser.add_argument('--overwrite-pw', action='store_true', help='Don\'t read anything from the keystore and prompt for new passwords.')
parser.add_argument('--change-ip', default=False, help='Path to a yaml file to change IPs.')
parser.add_argument('--ping', action='store_true', help='Test connection to each host. Don\'t do anything else.')
parser.add_argument('--generate-only', '-g', action='store_true', help='Don\'t connect to any remote host or install on local machine. Only generate configs and certs.')
parser.add_argument('--sfx', '-s', action='store_true', help='Create self-extracting installers to install on the hosts.')
parser.add_argument('--hosts', default=[], nargs='*', help='Only do these hosts.')
args = parser.parse_args()


# TODO: embed the certs inside the config file???


def download_file(url: str, output_path: str):
    # local_filename = os.path.join(target_dir, url.split('/')[-1])
    local_filename = output_path
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                # if chunk:
                f.write(chunk)
    return local_filename


def append_to_start_of_file(file: Union[str, Path], *write_lines):
    file = open(file, 'r+')
    lines = file.readlines()
    file.seek(0)
    for new in write_lines:
        file.write(str(new) + '\n')
    for line in lines:
        file.write(line)
    file.close()


def get_ssh_port(host):
    if 'ssh' in host and 'port' in host['ssh']:
        return host['ssh']['port']
    else:
        return 22


def get_ssh_username(host):
    if 'ssh' in host and 'username' in host['ssh']:
        return host['ssh']['username']
    elif 'ssh' in config and 'username' in config['ssh']:
        return config['ssh']['username']
    else:
        return ''


def reload_nebula(restart_type, use_sudo=True):
    print(f'{restart_type.capitalize()}ing Nebula service...')
    reload_nebula_cmd = None  # make pycharm happy
    if restart_type == 'reload':
        reload_nebula_cmd = nebula_service_cmd('reload', use_sudo)
    elif restart_type == 'restart':
        reload_nebula_cmd = nebula_service_cmd('restart', use_sudo)
    else:
        raise ValueError
    if conn:
        if use_sudo:
            reload = conn.sudo(reload_nebula_cmd, print_err=True).return_code
        else:
            reload = conn.execute(reload_nebula_cmd, print_err=True).return_code
    else:
        reload = subprocess.run(reload_nebula_cmd, shell=True).returncode
    if reload > 0:
        print('Failed to reload Nebula service, code:', reload)
    time.sleep(2)  # sleep for a bit so we don't spam the service


def bulk_build_config(hosts, base_config, host_base_config, type: str = None):
    if not args.ping:
        for hostname, host in hosts.items():
            created = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
            host_conf = host_builder.build_config(hostname, deepcopy(base_config), deepcopy(host_base_config), deepcopy(host))
            out_file = config_output_dir / f'{type + "-" if type is not None else ""}{hostname}.yml'
            with open(out_file, 'w') as file:
                yaml.safe_dump(host_conf, file, default_flow_style=False)
            verify_str = f'{uuid4()}-{uuid4()}'
            append_to_start_of_file(out_file, f'# Nebula hostname: {hostname}', f'# nebula_ip: {host["nebula_ip"]}', f'# Type: {type}', f'# groups: {", ".join(host["groups"])}', f'# Config built: {created}', f'# {verify_str}', '')
            config_to_ip.append({
                'host': host["nebula_ip"],
                'port': get_ssh_port(host),
                'username': get_ssh_username(host),
                'config_file': out_file,  # 'config': host_conf,
                'hostname': hostname,
                'verify': verify_str,
                'type': type,
                'groups': host['groups'],
                'arch': host.get('arch', 'linux-amd64'),
                'init': host.get('init', 'systemd'),
                'skip_connection': host.get('skip_connection', False),
                'use_sudo': (host['ssh'].get('use_sudo', True) if 'ssh' in host.keys() else True),
            })


def download_nebula(arch):
    print(arch)
    url = f'{nebula_latest}/nebula-{arch}.tar.gz'
    tmp_file = str(tempfile.mkstemp()[1])
    tmp_dir = Path(tempfile.mkdtemp())
    download_file(urllib.parse.urljoin(url, urllib.parse.urlparse(url).path.replace('//', '/')), tmp_file)
    subprocess.run(f'tar -xzf "{tmp_file}" -C "{tmp_dir}"', shell=True)
    os.remove(tmp_file)
    return tmp_dir


log_level = logging.INFO if args.verbose else logging.CRITICAL

logger.setLevel(log_level)

args.config = Path(args.config).expanduser().absolute().resolve()
args.files = Path(args.files).expanduser().absolute().resolve()
nebula_paths = NebulaPaths(args.files)
config = NebulaNetworkConfig(args.config).config

if len(args.hosts) == 0:
    hosts = config['hosts']
    lighthouses = config['lighthouses']
else:
    hosts = {}
    lighthouses = {}
    for host in args.hosts:
        if host in config['hosts'].keys():
            hosts.update({host: config['hosts'][host]})
        elif host in config['lighthouses'].keys():
            lighthouses.update({host: config['lighthouses'][host]})

config_output_dir = Path(config['config_output_dir']).expanduser().absolute().resolve()
config_output_dir.mkdir(parents=True, exist_ok=True)
sfx_output_dir = Path(config['sfx_output_dir']).expanduser().absolute().resolve()
sfx_output_dir.mkdir(parents=True, exist_ok=True)

host_builder = HostBuilder(nebula_paths)
certs_builder = NebulaCerts(
    ca_cert=config['certs']['ca_cert'],
    ca_key=config['certs']['ca_key'],
    out_dir=Path(config['certs']['output_dir']).expanduser().absolute().resolve(),
    subnet_size=config['subnet_prefix_size'],
)
ca_cert_path, ca_crt = certs_builder.read_ca_crt()

print('Building configs...')
# Build hosts
bulk_build_config(hosts, host_builder.base, host_builder.host_base, type='host')

# Build lighthouses
bulk_build_config(lighthouses, host_builder.base, host_builder.lighthouse_base, type='lighthouse')

# Create a local known_hosts file
# known_hosts_file = (args.files / 'known_hosts')
# known_hosts_file.touch()

failed_connections = []

sudo_passwords = Passwords()
usernames = []
if config['ssh']['ask_sudo']:
    for machine in config_to_ip:
        if machine['username'] not in usernames:
            pw = sudo_passwords.get(machine['username'])
            if pw is None or args.overwrite_pw:
                print('sudo password not saved for username:', machine['username'])
                sudo_passwords.prompt(machine['username'])
            else:
                print('Retrieved sudo password for username:', machine['username'])
            usernames.append(machine['username'])

change_ip_file = Path('change_ip.yml')
change_ip_config = {}
if change_ip_file.exists():
    with open(change_ip_file, 'r') as file:
        change_ip_config = yaml.safe_load(file)

nebula_arches = {}
if args.sfx:
    print('Downloading Nebula...')

    #    conf_arch_to_nebula_releases = {
    #        'armv7': nebula_armv7,
    #        'amd64': nebula_amd64,
    #        'mips':
    #    }

    # Check for other arches
    arches = []
    for machine in config_to_ip:
        if machine.get('arch'):
            # arch_resolved = conf_arch_to_nebula_releases[machine.get('arch')]
            arches.append(machine.get('arch'))
            #           if not nebula_arches.get(arch_resolved):
            #               nebula_arches[arch_resolved] = {
            #                   'hosts': [machine['hostname']],
            #                   'path': None,
            #               }
            #           else:
            if machine.get('arch') not in nebula_arches.keys():
                nebula_arches[machine.get('arch')] = {}
            if 'hosts' not in nebula_arches[machine.get('arch')].keys():
                nebula_arches[machine.get('arch')]['hosts'] = []
            nebula_arches[machine.get('arch')]['hosts'].append(machine['hostname'])

    for arch in arches:
        if not nebula_arches.get(arch).get('path'):
            if arch != 'none':
                nebula_arches[arch]['path'] = download_nebula(arch)  # print(nebula_arches)  # import sys  # sys.exit()
            else:
                nebula_arches[arch]['path'] = None

# Upload the files
for machine in config_to_ip:
    print('\n=================================')
    new_ip = None
    conn = None  # make pycharm happy
    local_machine = False
    nebula_ip = machine['host']

    print(machine['hostname'], nebula_ip)

    try:

        if not args.generate_only:
            if machine['hostname'] in change_ip_config.keys():
                new_ip = change_ip_config[machine['hostname']]['new_ip']
                nebula_ip = change_ip_config[machine['hostname']]['nebula_ip']

            print('Changing IP to', new_ip) if new_ip is not None else None
            print()

        # Generate the keys before connecting so the user has them locally and if the connection fails he can install them manually.
        host_crt_path, host_crt, host_key_path, host_key = certs_builder.read_host_certs(machine['hostname'], machine['type'])
        if (args.generate_certs or not host_crt_path.exists() or not host_key_path.exists()) and not args.ping:
            print('Generating new cert...')
            certs_builder.create_new(name=machine['hostname'], ip=nebula_ip if not new_ip else new_ip, groups=machine['groups'], type=machine['type'], overwrite=True)

        if args.sfx:
            for k, v in nebula_arches.items():
                for x in v['hosts']:
                    if x == machine['hostname']:
                        print(f'Creating self-extracting installer for {k}...')
                        create_installer_archive(machine['hostname'], sfx_output_dir, machine['config_file'], host_key_path, host_crt_path, ca_cert_path, v['path'], init_type=machine['init'])

        if not args.generate_only:
            if machine['skip_connection']:
                print('Skipping connecting...')
                continue

            # Skip local machine
            if nebula_ip in get_ip_addresses():
                print(nebula_ip, 'is us! :)')
                local_machine = True
                conn = None
            else:
                print('Connecting to', nebula_ip)
                local_machine = False
                conn = NebulaSSH(host=nebula_ip, username=machine['username'], port=machine['port'],  # known_hosts_file=known_hosts_file,
                                 timeout=config['ssh']['timeout'], sudo_password=sudo_passwords.get(machine['username']), )
                if not conn.check_host_up():
                    print('Host', nebula_ip, 'is down on port 22.')
                    failed_connections.append((machine['hostname'], nebula_ip, 'Port 22 down.'))
                    continue
                conn.connect()
                if not conn:
                    print('Failed to connect to', nebula_ip)
                    failed_connections.append((machine['hostname'], nebula_ip, 'Could not create connection.'))
                    continue
                print('Connected to host:', conn.execute('hostname', print_err=True).stdout.strip())
            if args.ping:
                continue

            print('Installing config...')
            config_file = Path(machine['config_file']).read_text()
            cmd_install = install_config(config_file, use_sudo=machine['use_sudo'])
            # print(cmd_install)
            if conn:
                if machine['use_sudo']:
                    config_install = conn.sudo(cmd_install, print_err=True)
                else:
                    config_install = conn.execute(cmd_install, print_err=True)
                if not config_install or config_install.return_code:
                    print('Failed for host', nebula_ip)
                    failed_connections.append((machine['hostname'], nebula_ip, 'Config install failed.'))
                    continue
            else:
                subprocess.run(cmd_install, shell=True)

            # TODO: check hash instead of the value
            cmd_verify = 'cat /etc/nebula/config.yaml'
            if conn:
                verify = conn.execute(cmd_verify, print_err=True).stdout
            else:
                verify = subprocess.check_output(cmd_verify, shell=True).decode()
            if machine['verify'] not in verify:
                print('FAILED TO VERFIY INSTALLED CONFIG! String not found!')
                failed_connections.append((machine['hostname'], nebula_ip, 'Failed to verify config.'))
            else:
                print('Config installed and verified.')

        if args.generate_certs:
            # print('Generating new cert...')
            # certs_builder.create_new(name=machine['hostname'], ip=nebula_ip if not new_ip else new_ip, groups=machine['groups'], type=machine['type'], overwrite=True)
            if not args.generate_only:
                print('Installing new cert...')
                cert_install_cmd = install_cert(ca_crt, host_crt, host_key, use_sudo=machine['use_sudo'])
                if conn:
                    fail = False
                    for cmd in cert_install_cmd:
                        x = conn.execute(cmd, sudo=machine['use_sudo'], print_err=True)
                        if not x or x.return_code:
                            print('Failed for host', nebula_ip)
                            print('Failed on cmd:', cmd)
                            failed_connections.append((machine['hostname'], nebula_ip, 'Failed to install config.'))
                            fail = True
                            break
                    if fail:
                        continue
                else:
                    fail = False
                    for action in cert_install_cmd:
                        s = subprocess.run(action, shell=True)
                        if s.returncode:
                            print('Failed on command:', action)
                            print('stdout:', s.stdout)
                            print('stderr:', s.stderr)
                            failed_connections.append((machine['hostname'], nebula_ip, 'Local subprocess command failed.'))
                            fail = True
                            break
                    if fail:
                        continue

        if not args.ping and not args.generate_only:
            reload_nebula('restart' if new_ip else args.restart_type, use_sudo=machine['use_sudo'])
            if local_machine:
                # TODO: watch interfaces for an ip matching this machine's nebula IP in the config
                print('Waiting 10s to let link come back up...')
                time.sleep(10)
        conn.close() if conn is not None else None
    except Exception as e:
        print('EXCEPTION:', e)
        print(traceback.format_exc())
        failed_connections.append((machine['hostname'], nebula_ip, e))

print('\n=================================')
print('\nDone!')

print('\nFailed:')
if len(failed_connections):
    for x, y, z in failed_connections:
        print(f'{x} | {y} | {z}')
else:
    print('none!')

if args.sfx:
    for k, v in nebula_arches.items():
        if v['path']:
            shutil.rmtree(v['path'])
