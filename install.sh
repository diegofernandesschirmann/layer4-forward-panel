#!/bin/bash

apt update

apt install -y \
    haproxy \
    python3 \
    python3-pip \
    ufw

mkdir -p /opt/port-panel
