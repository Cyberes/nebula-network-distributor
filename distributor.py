#!/usr/bin/env python3
import argparse
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Union
from uuid import uuid4

import yaml

from nebula_distributor import NebulaNetworkConfig, NebulaPaths, HostBuilder, Passwords, NebulaCerts
from nebula_distributor.commands import install_config, reload_nebula_cmd, install_cert, restart_nebula_cmd
from nebula_distributor.ssh import NebulaSSH
from nebula_distributor.ssh import get_ip_addresses

script_directory = os.path.abspath(os.path.dirname(__file__))
config_to_ip = []


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


def reload_nebula(restart_type=None):
    if not restart_type:
        restart_type = args.restart_type
    print(f'{restart_type.capitalize()}ing Nebula service...')
    if conn:
        reload = conn.sudo(reload_type_cmd).return_code
    else:
        reload = subprocess.run(reload_type_cmd, shell=True).returncode
    if reload > 0:
        print('Failed to reload Nebula service, code:', reload)
    time.sleep(2)  # sleep for a bit so we don't spam the service


def bulk_build_config(hosts, base_config, host_base_config, type: str = None):
    for hostname, host in hosts.items():
        created = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        host_conf = host_builder.build_config(hostname, base_config, host_base_config, host['groups'])
        out_file = config_output_dir / f'{type + "-" if type is not None else ""}{hostname}.yml'
        if not args.test_connection:
            with open(out_file, 'w') as file:
                yaml.dump(host_conf, file, default_flow_style=False)
        verify_str = f'{uuid4()}-{uuid4()}'
        append_to_start_of_file(out_file, f'# Nebula hostname: {hostname}', f'# nebula_ip: {host["nebula_ip"]}', f'# Type: {type}', f'# groups: {", ".join(host["groups"])}', f'# Config built: {created}', f'# {verify_str}', '')
        config_to_ip.append({
            'host': host["nebula_ip"],
            'port': get_ssh_port(host),
            'username': get_ssh_username(host),
            'config_file': out_file,
            # 'config': host_conf,
            'hostname': hostname,
            'verify': verify_str,
            'type': type,
            'groups': host['groups'],
        })


parser = argparse.ArgumentParser(
    description='Nebula Network Distributor: an easy way to distribute configs and certs to your Nebula network.'
)
parser.add_argument('--config', default=Path(script_directory, 'config.yml'), help='Path to config.yml if it is not located next to this executable.')
parser.add_argument('--files', default=Path(script_directory, 'files'), help='Path to the nebula-files directory if it is not located next to this executable.')
parser.add_argument('--log', default=False, help='Log to this file.')
parser.add_argument('--restart-type', required=False, default='reload', choices=['reload', 'restart'], help='How to restart the Nebula service on the remote host.')
parser.add_argument('--test-connection', action='store_true', help='Only test connection to each server.')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('-d', '--daemon', action='store_true', help='Start in daemon mode.')
parser.add_argument('-g', '--generate-certs', action='store_true', help='Generate and install new certs for each host.')
parser.add_argument('--overwrite-pw', action='store_true', help='Don\'t read anything from the keystore and prompt for new passwords.')
parser.add_argument('--change-ip', default=False, help='Path to a yaml file to change IPs.')
parser.add_argument('--ping', action='store_true', help='Test connection to each host. Don\'t do anything else.')
args = parser.parse_args()

args.config = Path(args.config).expanduser().absolute().resolve()
args.files = Path(args.files).expanduser().absolute().resolve()
if args.restart_type == 'reload':
    reload_type_cmd = reload_nebula_cmd
elif args.restart_type == 'restart':
    reload_type_cmd = restart_nebula_cmd
else:
    raise Exception

nebula_paths = NebulaPaths(args.files)
config = NebulaNetworkConfig(args.config).config
hosts = config['hosts']
lighthouses = config['lighthouses']

config_output_dir = Path(config['config_output_dir']).expanduser().absolute().resolve()
config_output_dir.mkdir(parents=True, exist_ok=True)

host_builder = HostBuilder(nebula_paths)
certs_builder = NebulaCerts(
    ca_cert=config['certs']['ca_cert'],
    ca_key=config['certs']['ca_key'],
    out_dir=Path(config['certs']['output_dir']).expanduser().absolute().resolve(),
    subnet_size=config['subnet_prefix_size'],
)
ca_crt = certs_builder.read_ca_crt()

# Build hosts
bulk_build_config(hosts, host_builder.base, host_builder.host_base, type='host')

# Build lighthouses
bulk_build_config(lighthouses, host_builder.base, host_builder.lighthouse_base, type='lighthouse')

# Create a local known_hosts file
known_hosts_file = (args.files / 'known_hosts')
known_hosts_file.touch()

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

# Upload the files
for machine in config_to_ip:
    print('\n=================================')
    new_ip = None
    nebula_ip = machine['host']
    if machine['hostname'] in change_ip_config.keys():
        new_ip = change_ip_config[machine['hostname']]['new_ip']
        nebula_ip = change_ip_config[machine['hostname']]['nebula_ip']

    print(machine['hostname'], nebula_ip)
    print('Changing IP to', new_ip) if new_ip is not None else None
    print()

    # Generate the keys before connecting so the user has them locally and if the connection fails he can install them manually.
    if args.generate_certs and not args.ping:
        print('Generating new cert...')
        certs_builder.create_new(name=machine['hostname'], ip=nebula_ip if not new_ip else new_ip, groups=machine['groups'], type=machine['type'], overwrite=True)

    # Skip local machine
    if nebula_ip in get_ip_addresses():
        print('Not connecting to', nebula_ip, "since that's us.")
        local = True
        conn = None
    else:
        print('Connecting to', nebula_ip)
        local = False
        conn = NebulaSSH(
            host=nebula_ip,
            username=machine['username'],
            port=machine['port'],
            known_hosts_file=known_hosts_file,
            timeout=config['ssh']['timeout'],
            sudo_password=sudo_passwords.get(machine['username']),
        )
        if not conn.check_host_up():
            print('Host', nebula_ip, 'is down on port 22.')
            failed_connections.append((machine['hostname'], nebula_ip))
            continue
        conn.connect()
        if not conn:
            print('Failed to connect to', nebula_ip)
            continue
        print('Connected to host:', conn.execute('hostname').stdout.strip())
    if args.ping:
        continue

    print('Installing config...')
    config_file = Path(machine['config_file']).read_text()
    cmd_install = install_config(config_file)
    if conn:
        config_install = conn.sudo(cmd_install)
        if not config_install or config_install.return_code:
            print('Failed for host', nebula_ip)
            continue
    else:
        subprocess.run(cmd_install, shell=True)

    cmd_verify = 'cat /etc/nebula/config.yaml'
    if conn:
        verify = conn.execute(cmd_verify).stdout
    else:
        verify = subprocess.check_output(cmd_verify, shell=True).decode()
    if machine['verify'] not in verify:
        print('FAILED TO VERFIY INSTALLED CONFIG! String not found!')
    else:
        print('Config installed and verified.')

    if args.generate_certs:
        # print('Generating new cert...')
        # certs_builder.create_new(name=machine['hostname'], ip=nebula_ip if not new_ip else new_ip, groups=machine['groups'], type=machine['type'], overwrite=True)
        host_crt, host_key = certs_builder.read_host_certs(machine['hostname'], machine['type'])
        print('Installing new cert...')
        cert_install_cmd = install_cert(ca_crt, host_crt, host_key)
        if conn:
            fail = False
            for cmd in cert_install_cmd:
                x = conn.execute(cmd, sudo=True)
                if not x or x.return_code:
                    print('Failed for host', nebula_ip)
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
                    fail = True
                    break
            if fail:
                continue

    reload_nebula('restart' if new_ip else 'reload')

print('\n=================================')
print('\nDone!')

print('\nFailed connections:')
for x, y in failed_connections:
    print(x, y)
