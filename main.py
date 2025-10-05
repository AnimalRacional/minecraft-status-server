import logging
import socketserver
import varint
from io import BytesIO
import struct
from util import make_status_response
from os import environ
from json import dumps
from PIL import Image
import base64

logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')

class StatusServerHandler(socketserver.BaseRequestHandler):
    def __init__(self, request, client_address, server) -> None:
        self.logger = logging.getLogger('StatusServerHandler')
        #self.logger.debug(f'__init__: CLIADDR: {client_address}, REQ: {request}, SERVER: {server}')
        self.stream = BytesIO(bytearray(512))
        return super().__init__(request, client_address, server)
    def setup(self):
        return super().setup()
    def read_to_stream(self, n):
        self.logger.debug(f'initial tell: {self.stream.tell()}')
        if abs(self.stream.getbuffer().nbytes - self.stream.tell() < n):
            self.stream.write(b'0' * n)
            self.stream.seek(-n, 1)
            self.logger.debug(f'expand tell: {self.stream.tell()}')
        n = self.stream.write(self.request.recv(n))
        self.logger.debug(f'recvd {n}')
        self.stream.seek(-n, 1)
        self.logger.debug(f'final tell {self.stream.tell()}')
        return n
    def handle(self):
        self.logger.debug('Received request')
        readed = self.read_to_stream(32)
        packsize = varint.decode_stream(self.stream)
        self.logger.debug(f'packsize: {packsize} at {self.stream.tell()}')
        # return (host, port, intent, protocol_version)
        if packsize == 254:
            self.logger.debug('legacy')
            while readed < 0x36:
                readed += self.read_to_stream(32)
                self.logger.debug(f'now read {readed}')
            self.handle_legacy_ping()
        else:
            handshake_res = self.handle_handshake(self.stream)
            if handshake_res == None:
                return
            self.logger.info('received handshake, waiting for ping and request')
            for i in range(0,2):
                self.logger.debug('waiting for new message...')
                self.read_to_stream(256)
                self.logger.debug(f'received message')
                packet_size = varint.decode_stream(self.stream)
                self.logger.debug(f'size: {packet_size}')
                packet_id = self.stream.read(1)[0]
                if packet_id == 0x00:
                    self.logger.debug('status request')
                    self.handle_status_request(handshake_res[3])
                elif packet_id == 0x01:
                    self.logger.debug('got ping packet')
                    long = self.stream.read(8)
                    longval = int.from_bytes(long)
                    self.logger.debug(f'ping packet value: {longval}')
                    tosend = b''.join([bytes([len(long)+1, 0x01]), long])
                    self.logger.debug(f'pong: {tosend}')
                    self.request.send(tosend)
                else:
                    self.logger.error(f'got packet {packet_id} waiting for ping')
                    #self.request.send(bytes([0x09,0x01,0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80]))
                    return
        return super().handle()
    def finish(self):
        self.logger.debug('closed connection')
        return super().finish()
    def handle_legacy_ping(self):
        # handle legacy ping
        self.logger.debug('[{}]'.format(', '.join(hex(x) for x in list(self.stream.getbuffer()))))
        msg = '§1\x00' # string header
        version = environ.get('mcversion', '67.69')
        maxp = int(environ.get('mcmaxplr', '50'))
        onlp = int(environ.get('mconlineplr', '100'))
        motd = environ.get('mcmotd', '§da fake status server')
        proto = environ.get('mcproto', 'same')
        if proto == 'same':
            protocol = 127
        else:
            protocol = int(proto)
        msg += f'{str(protocol)}\x00{version}\x00{motd}\x00{str(onlp)}\x00{str(maxp)}\x00'
        msg = msg.encode('utf-16be')
        lngt = (len(msg)//2).to_bytes(2)
        packet = b'\xff' + lngt
        response = b''.join([packet, msg])
        self.logger.debug(f'responding with {response}')
        self.request.send(response)
    def handle_handshake(self, dstream):
        self.logger.info("Handling handshake")
        self.logger.debug(f'buffer: {list(self.stream.getvalue())}')
        packet_id = dstream.read(1)[0]
        if packet_id != 0:
            self.logger.debug(f"invalid request: handshake packet id was {packet_id}")
            self.request.send(b"closed")
            return None
        self.logger.debug('valid request')
        protocol_version = varint.decode_stream(dstream)
        strlen = varint.decode_stream(dstream)
        host = dstream.read(strlen).decode('utf-8')
        cport = dstream.read(2)
        port = struct.unpack('>H', cport)[0]
        intent = varint.decode_stream(dstream)
        self.logger.debug('Valid connection')
        self.logger.debug(f'protocol: {protocol_version}')
        self.logger.debug(f'address: {host}:{port}')
        self.logger.debug(f'intent: {intent}')
        return (host, port, intent, protocol_version)
    def handle_status_request(self, protocol_version):
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
        try:
            icon = self.server.servericon
        except AttributeError:
            icon = ''
            
        self.logger.debug(f'icon len: {len(icon)}')
        response = make_status_response(
            version, 
            protocol, 
            maxp, 
            onlp, 
            dumps(playerlist),
            motd,
            False,
            icon
            ).encode('utf-8')
        responselen = varint.encode(len(response))
        senddata = b''.join([bytes([0]), responselen, response])
        senddata = b''.join([varint.encode(len(senddata)), senddata])
        self.logger.debug(f'sending {senddata}')
        self.request.send(senddata)
    
class StatusServer(socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate, icon = None):
        self.logger = logging.getLogger('StatusServer')
        self.servericon = icon
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)


def main():
    logger = logging.getLogger('StatusMain')
    try:
        buff = BytesIO()
        Image.open(environ.get('mcicon', 'icon.png')).resize((64, 64), Image.Resampling.BILINEAR).save(buff, format='PNG')
        servericon = base64.b64encode(buff.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f'Couldn\'t open icon.png: {type(e)}')
        servericon = ''

    from sys import argv
    port = 8500
    if(len(argv) > 1):
        port = int(argv[1])
    address = ('localhost', port)
    server = StatusServer(address, StatusServerHandler, True, servericon)
    try:
        address = server.server_address
        logger.info(f'server on {address[0]}:{address[1]}')
        server.serve_forever()
    finally:
        logger.info('closing server')
        server.socket.close()



if __name__ == "__main__":
    main()
