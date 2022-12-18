import copy

import yaml

from .nebula_paths import NebulaPaths


class HostBuilder:
    """
    This is a class so we reduce the amount of times we load the stub .yaml files.
    """
    # base = {}
    # default = {}
    # host_base = {}
    # lighthouse_base = {}
    firewalls = {}

    def __init__(self, paths: NebulaPaths):
        self.paths = paths
        self.base = self.__load_stub(self.paths.stubs.base)
        self.default = self.__load_stub(self.paths.stubs.default)
        self.host_base = self.__load_stub(self.paths.stubs.host_base)
        self.lighthouse_base = self.__load_stub(self.paths.stubs.lighthouse_base)

        for file in self.paths.firewalls.path.iterdir():
            self.firewalls = self.merge_configs(self.__load_stub(file), self.firewalls)

    def build_config(self, hostname: str, base_config: dict, host_base_config: dict, groups) -> dict:

        # Use the base config as a starting point for the dict
        conf = self.merge_configs(base_config, host_base_config)
        for g in groups:
            if g in self.firewalls.keys():
                if 'outbound' in self.firewalls[g]:
                    conf['firewall']['outbound'] = append_firewall(conf['firewall']['outbound'], self.firewalls[g]['outbound'])
                if 'inbound' in self.firewalls[g]:
                    conf['firewall']['inbound'] = append_firewall(conf['firewall']['inbound'], self.firewalls[g]['inbound'])
        return conf

    @staticmethod
    def __load_stub(file: str) -> dict:
        with open(file, 'r') as file:
            return yaml.safe_load(file)

    @staticmethod
    def merge_configs(*configs: dict) -> dict:
        """
        Merge the configs together, overwriting values in order of presidence from least to most.
        Later items overwrite earlier items in the code below. We want the customer config to overwrite all possible values in the config.
        For example, in: merge_configs(shared, machine, customer)
        The order would be: least important <- semi-important <- most important
        """
        configs = copy.deepcopy(configs)
        main_config = {}
        for i in range(len(configs)):
            for k, v in configs[i].items():
                for x in range(i + 1, len(configs)):
                    if k in configs[x]:
                        if isinstance(configs[i][k], list) or isinstance(configs[i][k], dict):
                            main_config[k] = v
                            main_config[k].update(configs[x][k])
                            del configs[x][k]  # delete the merged array since we will merge the entire dict later and don't want to repeat
                        else:
                            main_config[k] = configs[x][k]
                    else:
                        main_config[k] = v
                main_config.update(configs[i])
        return main_config


def append_firewall(firewall_conf, new) -> dict:
    for item in new:
        firewall_conf.append(item)
    return firewall_conf
