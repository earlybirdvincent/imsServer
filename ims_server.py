#!/usr/local/bin/python
# -*- coding:UTF-8 -*-

import os
import SocketServer
import threading
import time
import sys
# import logging
import logging.config
import json
import platform
import socket

OPERATION_PLATFORM = platform.system()

try:
    with open('ims_logger_config.json', 'r') as f:
        DICT_LOG_CONFIG = json.load(f)
except:
    print 'open ims_logger_config file failed:\n    ', sys.exc_info()[0], sys.exc_info()[1]
    sys.exit(1)


try:
    logging.config.dictConfig(DICT_LOG_CONFIG)
    print 'dictLogConfig loaded'
except Exception:
    print 'loading LogConfig failed: \n    ', sys.exc_info()[0], sys.exc_info()[1]


# create logger
IMS_SERVER_LOGGER = logging.getLogger('imsServer')
RAW_MSG_LOGGER = logging.getLogger('rawMsg')

# logging.basicConfig(filename='imsServer.log',level=logging.DEBUG)


class ThreadedTcpRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        client_ip = self.client_address[0]
        client_port = self.client_address[1]
        IMS_SERVER_LOGGER.info('client connected: {}:{}'.format(client_ip, client_port))
        while True:
            try:
                data = self.request.recv(1024)
            except:
                IMS_SERVER_LOGGER.info('connection reset {}:{}'.format(client_ip, client_port))
                return

            if not data:
                IMS_SERVER_LOGGER.info('connection remotely closed '
                    '{}:{}'.format(client_ip, client_port))
                break
            elif data:
                RAW_MSG_LOGGER.info('message received from client '
                    'IP %s PORT:%s over TCP:\n'
                    '<start of the message>-------------------------\n'
                    '%s'
                    '\n<end of the message>---------------------------\n', client_ip, client_port, data)
                print data
                

                if OPERATION_PLATFORM == 'Windows':
                    current_thread = threading.currentThread()
                    IMS_SERVER_LOGGER.debug('%s is created.\nReceived message from '
                        'IP %s PORT:%s:\n%s\n', current_thread, client_ip, client_port, data)
                else:
                    current_pid = os.getpid()
                    IMS_SERVER_LOGGER.debug('PID: %s is created.\nReceived message from '
                        'IP %s PORT:%s\n%s\n', current_pid, client_ip, client_port, data)

                response = data.strip()
                try:
                    self.request.sendall(response)
                except Exception as e:
                    IMS_SERVER_LOGGER.info('Server failed to send response to client '
                        '{}:{}\n{}'.format(client_ip, client_port, e))
                    return
        return


class ThreadedUdpRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        client_ip = self.client_address[0]
        client_port = self.client_address[1]

        data = self.request[0].strip()

        RAW_MSG_LOGGER.info('message received from client IP '
            '%s PORT:%s over UDP:\n%s\n', client_ip, client_port, data)

        if OPERATION_PLATFORM == 'Windows':
            current_thread = threading.currentThread()
            IMS_SERVER_LOGGER.debug('%s is created.\n'
                'Received message:\n%s\n', current_thread, data)
        else:
            current_pid = os.getpid()
            IMS_SERVER_LOGGER.debug('PID: %s is created.\n'
                'Received message:\n%s\n', current_pid, data)
        udp_socket = self.request[1]
        udp_socket.sendto(data, self.client_address)

if OPERATION_PLATFORM == 'Windows':
    IMS_SERVER_LOGGER.debug('detected Windows platform. ThreadingMixIn will be used.')

    class ImsTcpServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        pass

    class ImsTcpServerV6(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        address_family = socket.AF_INET6

    class ImsUdpServer(SocketServer.ThreadingMixIn,SocketServer.UDPServer):
        pass

    class ImsUdpServerV6(SocketServer.ThreadingMixIn,SocketServer.UDPServer):
        address_family = socket.AF_INET6

else:
    IMS_SERVER_LOGGER.debug('Non-Windows platform. ForkingMixIn will be used.')

    class ImsTcpServer(SocketServer.ForkingMixIn, SocketServer.TCPServer):
        pass

    class ImsTcpServerV6(SocketServer.ForkingMixIn, SocketServer.TCPServer):
        address_family = socket.AF_INET6

    class ImsUdpServer(SocketServer.ForkingMixIn,SocketServer.UDPServer):
        pass

    class ImsUdpServerV6(SocketServer.ForkingMixIn,SocketServer.UDPServer):
        address_family = socket.AF_INET6


def get_socket_type(server):
    if server.socket_type == 1:
        return 'TCP'
    elif server.socket_type == 2:
        return 'UDP'
    else:
        return 'Unknown socket type.'


def main():
    try:
        with open('ims_server_config2.json') as f:
            dict_ims_server_config = json.load(f)
    except:
        dict_ims_server_config = {
            'server_ipv4':['localhost'],
            'server_ipv6':['::1'],
            'port':[5060]
        }
        IMS_SERVER_LOGGER.exception('open ims_server_config file failed. IMS server '
        'will use default value:\n    {}'.format(dict_ims_server_config))

    servers = []

    for server_ipv4 in dict_ims_server_config['server_ipv4']:
        for server_port in dict_ims_server_config['port']:
            address = (server_ipv4, server_port)
            try:
                servers.append(ImsTcpServer(address, ThreadedTcpRequestHandler))
                servers.append(ImsUdpServer(address, ThreadedUdpRequestHandler))
            except socket.error as e:
                IMS_SERVER_LOGGER.error('{}: {}'.format(e, address))
                
    for server_ipv6 in dict_ims_server_config['server_ipv6']:
        for server_port in dict_ims_server_config['port']:
            address_ipv6 = (server_ipv6, server_port)
            try:
                servers.append(ImsTcpServerV6(address_ipv6, ThreadedTcpRequestHandler))
                servers.append(ImsUdpServerV6(address_ipv6, ThreadedUdpRequestHandler))
            except socket.error as e:
                IMS_SERVER_LOGGER.error('{}: {}'.format(e, address_ipv6))

    for s in servers:
        thread = threading.Thread(target=s.serve_forever)
        thread.setDaemon(True)
        thread.start()
        server_address = s.server_address
        IMS_SERVER_LOGGER.info('server started: {} {}'.format(server_address, get_socket_type(s)))

    try:
        while 1:
            time.sleep(1)
            sys.stderr.flush()
            sys.stdout.flush()

    except KeyboardInterrupt:
        pass
    finally:
        for s in servers:
            s.shutdown()




if __name__ == '__main__':
    main()