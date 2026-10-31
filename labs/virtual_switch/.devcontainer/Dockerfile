FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Networking tools for the lab: namespaces/veth (iproute2), traffic (ping, arping),
# capture (tcpdump, tshark), offload tuning (ethtool) and libpcap for scapy.
# The base image ships a Yarn apt source with an expired signing key; we do not
# need Yarn, so drop it or `apt-get update` fails.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        iproute2 iputils-ping arping tcpdump tshark ethtool libpcap0.8 net-tools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installed system-wide so both the vscode user and `sudo python` see the same packages.
COPY requirements.txt requirements-dev.txt /tmp/pip/
RUN pip install --no-cache-dir -r /tmp/pip/requirements-dev.txt \
    && rm -rf /tmp/pip
