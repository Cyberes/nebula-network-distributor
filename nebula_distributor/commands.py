from typing import Union, Tuple

import yaml


def build_file_write(content, file) -> str:
    return f"""echo '''{content.strip()}''' | sudo tee {file} > /dev/null"""


def install_cert(ca_crt, host_crt, host_key) -> Tuple[str, str, str]:
    return (
        build_file_write(ca_crt, '/etc/nebula/ca.crt'),
        build_file_write(host_crt, '/etc/nebula/host.crt'),
        build_file_write(host_key, '/etc/nebula/host.key'),
    )


def install_config(config: Union[dict, str]) -> str:
    if isinstance(config, dict):
        config = yaml.dump(config, default_flow_style=False)
    return build_file_write(config, '/etc/nebula/config.yaml')


def nebula_service_cmd(action):
    return f'sudo service nebula {action}'


reload_nebula_cmd = nebula_service_cmd('reload')
restart_nebula_cmd = nebula_service_cmd('restart')
