import sentinel
import yaml
from mergedeep import merge, Strategy  # https://mergedeep.readthedocs.io/en/latest/

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
        self.base = self.__load_stub(self.paths.base_configs.base)
        self.default = self.__load_stub(self.paths.base_configs.default)
        self.host_base = self.__load_stub(self.paths.base_configs.host_base)
        self.lighthouse_base = self.__load_stub(self.paths.base_configs.lighthouse_base)

        for file in self.paths.firewalls.path.iterdir():
            self.firewalls = merge(self.__load_stub(file), self.firewalls)

        self.extras = {}
        for file in self.paths.extras.path.iterdir():
            conf = self.__load_stub(file)
            if conf:  # don't load an empty file
                self.extras[file.stem] = conf

        self.override_files = {}
        self.overrides = []
        for file in self.paths.overrides.path.iterdir():
            conf = self.__load_stub(file)
            if conf:
                self.override_files[file.stem] = conf
                self.overrides.append(conf)

    def build_config(self, hostname: str, base_config: dict, host_base_config: dict, host: dict) -> dict:
        """
        Build a config for a host.
        """

        groups = host['groups']
        # Use the base config as a starting point for the dict
        conf = merge(base_config, host_base_config)

        extras_to_apply = {}
        for g in host['groups']:
            for name, extra in self.extras.items():
                if 'groups' in extra:
                    if g in extra['groups']:
                        conf = merge(conf, extra['extra'], strategy=Strategy.ADDITIVE)
                else:
                    raise KeyError(f'Missing `groups` key in extra: {extra}')

        for g in groups:
            if g in self.firewalls.keys():
                if 'outbound' in self.firewalls[g]:
                    conf['firewall']['outbound'] = append_firewall(conf['firewall']['outbound'], self.firewalls[g]['outbound'])
                if 'inbound' in self.firewalls[g]:
                    conf['firewall']['inbound'] = append_firewall(conf['firewall']['inbound'], self.firewalls[g]['inbound'])

        if 'overrides' in host and host['overrides'] and len(host['overrides']) > 0:
            # Override based on filename
            for o in host['overrides']:
                if o in self.override_files.keys():
                    conf = merge(conf, self.override_files[o])

        if conf.get('preferred_ranges'):
            conf['preferred_ranges'] = list(set(conf['preferred_ranges']))
        return dict(conf)

    @staticmethod
    def __load_stub(file: str) -> dict:
        with open(file, 'r') as file:
            return yaml.safe_load(file)


def append_firewall(firewall_conf, new) -> dict:
    for item in new:
        firewall_conf.append(item)
    return firewall_conf


def get_overriding_dict(input_dict: dict) -> dict:
    to_override = {}
    for k, v in input_dict.items():
        if isinstance(v, dict):
            for item, v_v in v.items():
                to_override[item] = v_v
        else:
            to_override = v
    return to_override


def finditem(obj, key):
    Missing = sentinel.create()
    if key in obj: return obj[key]
    for k, v in obj.items():
        if isinstance(v, dict):
            item = finditem(v, key)
            if item is not None:
                return item
    return Missing
