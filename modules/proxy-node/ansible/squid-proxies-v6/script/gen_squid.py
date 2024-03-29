# -*- coding: utf-8 -*-
import argparse
import crypt
import grp
import os
import pwd
import string
import secrets
import netifaces as ni
from ipaddress import IPv6Network, IPv6Address
from random import seed, getrandbits, choices, choice

from passlib.apache import HtpasswdFile

parser = argparse.ArgumentParser(description='Gen Squid Config')
parser.add_argument('--ipv6_subnet_full', help='ipv6 subnet full', required=True)
parser.add_argument('--net_interface', help='net interface', required=True)
parser.add_argument('--pool_name', help='pool name', default='squidv6')
parser.add_argument('--number_ipv6', help='number ipv6. Default = 250', default=250, type=int)
parser.add_argument('--unique_ip', help='single ip for each /64 subnet. Default = 1', default=1, type=int)
parser.add_argument('--start_port', help='start proxy port. Default 32000', default=32000, type=int)

args = parser.parse_args()

ipv6_subnet_full = args.ipv6_subnet_full
net_interface = args.net_interface
number_ipv6 = args.number_ipv6
unique_ip = args.unique_ip
start_port = args.start_port
pool_name = args.pool_name

sh_add_ip = f'/opt/v6proxies/add_ip_{pool_name}.sh'

def gen_ipv6(ipv6_subnet):
    seed()
    network = IPv6Network(ipv6_subnet)
    return IPv6Address(network.network_address + getrandbits(network.max_prefixlen - network.prefixlen))

def writeFile(pathToFile, textToWrite):
    if os.path.exists(path=pathToFile):
        os.remove(path=pathToFile)
        print("%s exists. Removed" % pathToFile)
    with open(pathToFile, 'a') as the_file:
        the_file.write(textToWrite + '\n')


def add_ipv6(num_ips, unique_ip=1):
    # if num_ips > 250:
    #     num_ips = 250
    list_ipv6 = []
    network2 = IPv6Network(ipv6_subnet_full)
    list_network2 = list(network2.subnets(new_prefix=64))
    # netplan_cmd_format = int_ip + "/24"

    if os.path.exists(path=sh_add_ip):
        os.remove(path=sh_add_ip)
        print("%s exists. Removed" % sh_add_ip)

    if unique_ip == 1:

        subnet = choices(list_network2, k=num_ips)

        for sub in subnet:
            ipv6 = gen_ipv6(ipv6_subnet=sub)
            list_ipv6.append(str(ipv6))

            # netplan_cmd_format = netplan_cmd_format + "," + str(ipv6) + "/128"

            cmd = f'ip -6 addr add {ipv6} dev {net_interface}'
            with open(sh_add_ip, 'a') as the_file:
                the_file.write(cmd + '\n')

    else:
        subnet = choices(list_network2, k=10)

        for i in range(0, num_ips):
            sub = choice(subnet)
            ipv6 = gen_ipv6(ipv6_subnet=sub)
            list_ipv6.append(str(ipv6))
            # print(ipv6)
            # r_conn.sadd(pool_name, ipv6)
            # cmd = '/sbin/ifconfig %s inet6 add %s/64' % (net_interface, ipv6)
            # netplan_cmd_format = netplan_cmd_format + "," + ipv6 + "/128"
            cmd = f'ip -6 addr add {ipv6} dev {net_interface}'
            with open(sh_add_ip, 'a') as the_file:
                the_file.write(cmd + '\n')

    # netplan_cmd = '''
    # netplan set ethernets.{net_interface}.addresses=[{netplan_cmd_format}]
    # netplan apply'''.format(net_interface=net_interface, netplan_cmd_format=netplan_cmd_format)
    # writeFile(sh_add_ip, netplan_cmd)

    return list_ipv6


cfg_squid = '''
max_filedesc 500000
access_log          none
cache_store_log     none

# Hide client ip #
forwarded_for delete

# Turn off via header #
via off

# Deny request for original source of a request
follow_x_forwarded_for allow localhost
follow_x_forwarded_for deny all

# See below
request_header_access X-Forwarded-For deny all

request_header_access Authorization allow all
request_header_access Proxy-Authorization allow all
request_header_access Cache-Control allow all
request_header_access Content-Length allow all
request_header_access Content-Type allow all
request_header_access Date allow all
request_header_access Host allow all
request_header_access If-Modified-Since allow all
request_header_access Pragma allow all
request_header_access Accept allow all
request_header_access Accept-Charset allow all
request_header_access Accept-Encoding allow all
request_header_access Accept-Language allow all
request_header_access Connection allow all
request_header_access All deny all

cache           deny    all

acl to_ipv6 dst ipv6
http_access deny all !to_ipv6
{squid_conf_suffix}
{squid_conf_refresh}
{block_squidProxies}
http_access deny all

'''

squid_conf_refresh = '''
refresh_pattern ^ftp:       1440    20% 10080
refresh_pattern ^gopher:    1440    0%  1440
refresh_pattern -i (/cgi-bin/|\?) 0 0%  0
refresh_pattern .       0   20% 4320
'''

squid_conf_suffix = '''
# Common settings
acl SSL_ports port 443
acl Safe_ports port 80      # http
acl Safe_ports port 21      # ftp
acl Safe_ports port 443     # https
acl Safe_ports port 70      # gopher
acl Safe_ports port 210     # wais
acl Safe_ports port 1025-65535  # unregistered ports
acl Safe_ports port 280     # http-mgmt
acl Safe_ports port 488     # gss-http
acl Safe_ports port 591     # filemaker
acl Safe_ports port 777     # multiling http
acl CONNECT method CONNECT

http_access deny !Safe_ports

http_access deny CONNECT !SSL_ports

http_access allow localhost manager
http_access deny manager

auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/{pid}.auth

auth_param basic children 5
auth_param basic realm Web-Proxy
auth_param basic credentialsttl 1 hour
auth_param basic casesensitive off

http_access allow localhost


coredump_dir /var/spool/squid3
'''

cfg_threeProxy = '''
daemon
setuid {uid}
setgid {gid}

internal {int_ip}

# log /var/log/3proxy/3proxy.log
# logformat "%Y-%m-%d %H:%M:%S %I %O %U"
# rotate 10

maxconn 5

auth strong
users $"/etc/3proxy/3proxy.auth"
{block_threeProxies}
'''

if_stat = ni.ifaddresses(net_interface)
int_ip = ni.ifaddresses(net_interface)[ni.AF_INET][0]['addr']
print(if_stat[ni.AF_INET] + if_stat[ni.AF_INET6])

threeProxy_uid = pwd.getpwnam("3proxy").pw_uid
threeProxy_gid = grp.getgrnam("3proxy").gr_gid

squidProxies = ''''''
threeProxies = ''''''
ipv6 = add_ipv6(num_ips=number_ipv6, unique_ip=unique_ip)

threeProxies_auth = ''''''
credsAndIp = 'ip;port;user;password' + '\n'

auth_file = f'/etc/squid/{pool_name}.auth'
ht = HtpasswdFile(auth_file, new=True)
i = 0

for ip_out in ipv6:
    # username = ''.join(choice(string.ascii_lowercase + string.digits) for i in range(6))
    new_i = '%05d'%(int('00000') + i)
    username = 'floxys' + new_i
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(20))  # for a 20-character password

    squidProxy_format = '''
    http_port       {port}
    acl     p{port}  localport       {port}
    acl {user} proxy_auth {user}
    http_access allow {user} p{port}
    tcp_outgoing_address    {ip_out} p{port}
    '''.format(port=start_port, ip_out=ip_out, user=username)
    squidProxies += squidProxy_format + '\n'

    threeProxies_format = '''
allow {user}
socks -6 -p{port} -e{ip_out}
flush
    '''.format(port=start_port + number_ipv6, ip_out=ip_out, user=username)
    threeProxies += threeProxies_format + '\n'

    threeProxies_auth_format = '''{user}:CR:{password}'''.format(user=username, password=crypt.crypt(password, crypt.METHOD_MD5))
    threeProxies_auth += threeProxies_auth_format + '\n'

    credsAndIp_format = '''{ip_out};{port};{user};{password}'''.format(port=start_port, ip_out=ip_out, user=username, password=password)
    credsAndIp += credsAndIp_format + '\n'
    
    i += 1
    start_port += 1
    ht.set_password(username, password)

ht.save()

cfg_squid_gen = cfg_squid.format(pid=pool_name, squid_conf_refresh=squid_conf_refresh,
                                 squid_conf_suffix=squid_conf_suffix.format(pid=pool_name),
                                 block_squidProxies=squidProxies)
cfg_threeProxy_gen = cfg_threeProxy.format(int_ip=int_ip, uid=threeProxy_uid, gid=threeProxy_gid, block_threeProxies=threeProxies)

writeFile(f'/etc/squid/squid.conf', cfg_squid_gen)
writeFile(f'/etc/3proxy/3proxy.cfg', cfg_threeProxy_gen)
os.chown("/etc/3proxy/3proxy.cfg", threeProxy_uid, threeProxy_gid)
writeFile(f'/etc/3proxy/3proxy.auth', threeProxies_auth)
os.chown("/etc/3proxy/3proxy.auth", threeProxy_uid, threeProxy_gid)
writeFile(f'/opt/v6proxies/squid_auth.csv', credsAndIp)

print("=========================== \n")
print("\n \n")
print("Run two command bellow to start proxies")
print("\n \n")
print(f"bash {sh_add_ip}")
print("\n \n")
print("Create %d proxies. Port start from %d" % (number_ipv6, start_port))
