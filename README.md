# nebula-network-distributor

_An easy way to distribute configs and certs to your Nebula network._

I run a [Nebula network](https://github.com/slackhq/nebula) with around two dozen hosts. That's enough that it's tedious to manually configure each one but not enough to warrant something like Ansible.

I wrote this simple tool to construct configs from premade templates and push them out to the hosts.

### Features

-   Automated installation of new configs and keys.
-   Automated signing of new keys.
-   Automatically reload the host's Nebula service.
-   Daemon service to run as a server.
-   Securely store your sudo passwords using your operating system's keyring.



## Install

```bash
pip install -r requirements.txt
```

Make sure you have these libraries installed. They should come with your OS but I manually built Python3.10 so I didn't have them.

```bash
sudo python3 -m pip install --force-reinstall --no-cache-dir netifaces
sudo python3 -m pip install --force-reinstall --no-cache-dir secretstorage
```



## Use

-   Firewall settings are in `files/configs/firewalls`. The root key is the name of the group you want this to apply to.
-   Config stubs are in  `files/configs/stubs`.
    -   `base.yaml` is applied to all hosts.
    -   `default.yaml` is Nebula's default config, not used.
    -   `host-base.yaml` is applied to all non-lighthouse hosts.
    -   `lighthouse-base.yaml` is applied to all lighthouse hosts.




Copy `config.sample.yml` to `config.yml` and fill out the details.



Then run it with:

```bash
./distributor.py
```



To generate and install certs, do this:

```bash
./distributor.py --generate-certs
```
