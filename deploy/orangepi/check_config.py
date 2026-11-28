"""Validate the resolved board network and print the H5 port for the smoke test."""

import ipaddress
import json
import sys


def web_port(config):
    web = config["services"]["web"]
    ipam = config["networks"]["proxy"]["ipam"]["config"][0]
    subnet = ipaddress.IPv4Network(ipam["subnet"])
    pool = ipaddress.IPv4Network(ipam["ip_range"])
    proxy = ipaddress.IPv4Address(web["networks"]["proxy"]["ipv4_address"])
    gateway = ipaddress.IPv4Address(ipam.get("gateway") or subnet.network_address + 1)
    if not pool.subnet_of(subnet):
        raise ValueError("代理动态地址池必须位于代理子网内")
    if proxy not in subnet or proxy in pool or proxy in (subnet.network_address, subnet.broadcast_address, gateway):
        raise ValueError("代理 IP 必须是子网内、动态地址池外的可用主机地址，并避开网关")
    ports = [p["published"] for p in web["ports"] if p["target"] == 80]
    if len(ports) != 1 or not str(ports[0]).isdigit() or not 1 <= int(ports[0]) <= 65535:
        raise ValueError("网页端口必须是 1 至 65535 之间的单个端口")
    return int(ports[0])


if __name__ == "__main__":
    try:
        print(web_port(json.load(sys.stdin)))
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        sys.exit(f"板端 Compose 配置无效：{exc}")
