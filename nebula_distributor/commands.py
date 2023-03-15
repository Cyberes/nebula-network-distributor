from typing import Tuple, Union

import yaml


def build_file_write(content, file, use_sudo=True) -> str:
    return f"""echo '''{content.strip()}''' | {"sudo" if use_sudo else ""} tee {file} > /dev/null"""


def install_cert(ca_crt, host_crt, host_key, use_sudo=True) -> Tuple[str, str, str]:
    return (
        build_file_write(ca_crt, '/etc/nebula/ca.crt', use_sudo),
        build_file_write(host_crt, '/etc/nebula/host.crt', use_sudo),
        build_file_write(host_key, '/etc/nebula/host.key', use_sudo),
    )


def install_config(config: Union[dict, str], use_sudo=True) -> str:
    if isinstance(config, dict):
        config = yaml.dump(config, default_flow_style=False)
    return build_file_write(config, '/etc/nebula/config.yaml', use_sudo)


def nebula_service_cmd(action, use_sudo=True):
    return f'{"sudo" if use_sudo else ""} service nebula {action}'


reload_nebula_cmd = nebula_service_cmd('reload')
restart_nebula_cmd = nebula_service_cmd('restart')
