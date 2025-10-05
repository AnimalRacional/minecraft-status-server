import logging
import socketserver
import varint
from io import BytesIO
import struct
from util import make_status_response

logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')

class StatusServerHandler(socketserver.BaseRequestHandler):
    def __init__(self, request, client_address, server) -> None:
        self.logger = logging.getLogger('StatusServerHandler')
        #self.logger.debug(f'__init__: CLIADDR: {client_address}, REQ: {request}, SERVER: {server}')
        return super().__init__(request, client_address, server)
    def setup(self):
        return super().setup()
    def handle(self):
        self.logger.debug('Received request')
        data = self.request.recv(128)
        self.logger.debug(f'recv(): {data}')
        if data[0] == 0xfe:
            self.logger.debug('legacy')
            kicklen = b'\xff\xff\xff'
            header = b'\x00\xa7\x00\x31\x00\x00'
            msg = '47\x001.7.10\x00\xa7ccool server\x0050\x0051'.encode('utf-16be')
            response = b''.join([kicklen, header, msg])
            self.logger.debug(f'responding to legacy {response}')
            self.request.send(response)
        else:
            dstream = BytesIO(data)
            (packet_size, bytes_read) = varint.decode_stream(dstream)
            self.logger.debug(f'size: {packet_size}')
            packet_id = dstream.read(1)[0]
            if packet_id != 0:
                self.logger.debug(f"invalid request: handshake packet id was {packet_id}")
                self.request.send(b"closed")
                return
            self.logger.debug('valid request')
            (protocol_version, br) = varint.decode_stream(dstream)
            (strlen, br) = varint.decode_stream(dstream)
            host = dstream.read(strlen).decode('utf-8')
            cport = dstream.read(2)
            port = struct.unpack('>H', cport)[0]
            intent = varint.decode_stream(dstream)[0]
            self.logger.debug('Valid connection')
            self.logger.debug(f'protocol: {protocol_version}')
            self.logger.debug(f'address: {host}:{port}')
            self.logger.debug(f'intent: {intent}')
            from os import environ
            from json import dumps
            players = environ.get('players', 'Herobrine, Notch').split(' ')
            print(f'environ players: {players}')
            playerlist = []
            for p in players:
                playerlist.append({"name": p, "id": "0541ed27-7595-4e6a-9101-6c07f879b7b5"})
            version = environ.get('mcversion', '67.69')
            maxp = int(environ.get('mcmaxplr', '50'))
            onlp = int(environ.get('mconlineplr', '100'))
            motd = environ.get('mcmotd', '§da fake status server')
            proto = environ.get('mcproto', 'same')
            if proto == 'same':
                protocol = protocol_version
            else:
                protocol = int(proto)
            response = make_status_response(
                version, 
                protocol, 
                maxp, 
                onlp, 
                dumps(playerlist),
                motd
                ).encode('utf-8')
            responselen = varint.encode(len(response))[0]
            senddata = b''.join([bytes([0]), responselen, response])
            senddata = b''.join([varint.encode(len(senddata))[0], senddata])
            self.logger.debug(f'sending {senddata}')
            self.request.send(senddata)
            for i in range(0,2):
                data = self.request.recv(64)
                dstream = BytesIO(data)
                packet_size = varint.decode_stream(dstream)[0]
                self.logger.debug(f'size: {packet_size}')
                packet_id = dstream.read(1)[0]
                if packet_id == 0x00:
                    self.logger.debug('status request')
                elif packet_id == 0x01:
                    self.logger.debug('got ping packet')
                    long = dstream.read(8)
                    longval = int.from_bytes(long)
                    self.logger.debug(f'ping packet value: {longval}')
                    tosend = b''.join([bytes([len(long)+1, 0x01]), long])
                    self.logger.debug(f'pong: {tosend}')
                    self.request.send(tosend)
                else:
                    self.logger.error(f'got packet {packet_id} waiting for ping')
                    self.request.send(bytes([0x09,0x01,0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80]))
                    return
            
        return super().handle()
    def finish(self):
        self.logger.debug('closed connection')
        return super().finish()
    
class StatusServer(socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate):
        self.logger = logging.getLogger('StatusServer')
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)


def main():
    logger = logging.getLogger('StatusMain')
    from sys import argv
    port = 8500
    if(len(argv) > 1):
        port = int(argv[1])
    address = ('localhost', port)
    server = StatusServer(address, StatusServerHandler, True)
    try:
        address = server.server_address
        logger.info(f'server on {address[0]}:{address[1]}')
        server.serve_forever()
    finally:
        logger.info('closing server')
        server.socket.close()



if __name__ == "__main__":
    main()
