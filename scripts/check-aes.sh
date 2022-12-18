#!/bin/bash
# Some devices (like arm) don't have AES acceleration
grep aes < /proc/cpuinfo
