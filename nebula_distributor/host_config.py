import sys
from pathlib import Path
from typing import Union

import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    """
    https://stackoverflow.com/a/63215043
    """

    def construct_mapping(self, node, deep=False):
        mapping = []
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                print('Failed to load config! Duplicate key in config:', key)
                sys.exit(1)
            mapping.append(key)
        return super().construct_mapping(node, deep)


class NebulaNetworkConfig:
    config = {}

    def __init__(self, config_path: Union[str, Path], load: bool = True):
        self.config_path = config_path

        if load:
            self.load()

    def load(self):
        with open(self.config_path, 'r') as file:
            self.config = yaml.load(file, Loader=UniqueKeyLoader)
        self.verify_config(self.config)
        self.check_for_duplicate_hosts()

    def check_for_duplicate_hosts(self):
        nebula_ip_addrs = []
        hostnames = []
        for host, values in self.config['hosts'].items():
            hostnames.append(host)
            nebula_ip_addrs.append(values['nebula_ip'])
        found_dupe = False
        for i, ip in enumerate(nebula_ip_addrs):
            if nebula_ip_addrs.count(ip) >= 2:
                print(f'Failed to load config! Duplicate IP on {hostnames[i]}:', ip)
                found_dupe = True
        if found_dupe:
            sys.exit(1)

    def verify_config(self, conf):
        def check(key):
            if key not in conf.keys():
                print('Missing config item:', key)
                sys.exit(1)

        check('subnet_prefix_size')
        check('config_output_dir')
        check('hosts')
        check('lighthouses')

        # Empty arrays are always None in pyyaml.
        # Set it to a dict so we don't throw an error later.
        if not self.config['hosts']:
            self.config['hosts'] = {}
        if not self.config['lighthouses']:
            self.config['lighthouses'] = {}
