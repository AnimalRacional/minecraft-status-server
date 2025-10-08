import traceback
import base64
from json import dumps
from packet_handler import unsized_packet_handler, packet_handler, unsized_packet_handler, Packet, PacketServerHandler
from socket import socket
from socketserver import BaseRequestHandler, TCPServer
from os import environ
import logging
from io import BufferedIOBase, BytesIO
import varint
import struct
import uuid
from PIL import Image
try:
    import dotenv
    dotenv.load_dotenv()
finally:
    pass

logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')
servericon: str = ''


def make_status_response(version, protocol, maxplr, players, playerlist, motd, secure = False, icon = ''):
    msgobj = {
        "version": {
            "name": version,
            "protocol": protocol
        },
        "players": {
            "max": maxplr,
            "online": players,
            "sample": playerlist
        },
        "description": motd
    }
    if icon != '':
        msgobj['favicon'] = f"data:image/png;base64,{icon}"
    msgobj['enforcesSecureChat'] = "true" if secure else "false"
    msg = dumps(msgobj)
    print(f'status message: {msg}')
    return msg

def handle_handshake(logger, dstream: BufferedIOBase):
        protocol_version = varint.decode_stream(dstream)
        strlen = varint.decode_stream(dstream)
        host = dstream.read(strlen).decode('utf-8')
        cport = dstream.read(2)
        port = struct.unpack('>H', cport)[0]
        intent = varint.decode_stream(dstream)
        logger.info(f'protocol: {protocol_version}')
        logger.info(f'address: {host}:{port}')
        logger.info(f'intent: {intent}')
        return (host, port, intent, protocol_version)

def handle_status_request(stream: BufferedIOBase, protocol_version: int, logger, icon):
        players = environ.get('players', 'Herobrine Notch').split(' ')
        playerlist = []
        for p in players:
            playerlist.append({"name": p, "id": "0541ed27-7595-4e6a-9101-6c07f879b7b5"})
        version = environ.get('mcversion', 'Any version')
        maxp = int(environ.get('mcmaxplr', '50'))
        onlp = int(environ.get('mconlineplr', '100'))
        motd = environ.get('mcmotd', '§da fake status server')
        proto = environ.get('mcproto', 'same')
        if proto == 'same':
            protocol = protocol_version
        else:
            protocol = int(proto)

        logger.debug(f'icon len: {len(icon)}')
        response = make_status_response(
            version, 
            protocol, 
            maxp, 
            onlp, 
            playerlist,
            motd,
            False,
            icon
            ).encode('utf-8')
        responselen = varint.encode(len(response))
        senddata = b''.join([bytes([0]), responselen, response])
        senddata = b''.join([varint.encode(len(senddata)), senddata])
        logger.debug(f'sending {senddata}')
        return senddata
    
def handle_login_request(logger, stream: BufferedIOBase):
    namelen = varint.decode_stream(stream)
    if namelen > 16:
        logger.error(f'name too big: {namelen}')
        return b''
    name = stream.read(namelen).decode('utf-8')
    plruuid = stream.read(16)
    uuid.UUID(bytes = plruuid)
    logger.info(f'player login: {name} ({str(plruuid)})')
    responsemsg = environ.get('mckickreason', '§dStatus Server only!')
    if not (responsemsg.startswith('[') or responsemsg.startswith('{')):
        responsemsg = f'"{responsemsg}"'
    responsedata = responsemsg.encode('utf-8')
    response = b''.join([b'\x00', varint.encode(len(responsedata)), responsedata])
    response = b''.join([varint.encode(len(response)), response])
    return response

handshake_data = {}

@packet_handler(0)
def handshake_status_login(packet: Packet, client: socket, address):
    logger = logging.getLogger(f'Packet ({packet.id} s{packet.size} by {address})')
    if address not in handshake_data:
        logger.debug(f"handshake: {packet.id} sized {packet.size} by {address}")
        handshake_data[address] = handle_handshake(logger, packet.stream)
    elif handshake_data[address][2] == 1: # intent was status request
        logger.debug(f'status request: {packet.id} sized {packet.size} by {address}')
        protocol = handshake_data[address][3]
        data = handle_status_request(packet.stream, protocol, logger, servericon)
        client.send(data)
    elif handshake_data[address][2] == 2: # intent was login request
        logger.debug(f'login request: {packet.id} sized {packet.size} by {address}')
        response = handle_login_request(logger, packet.stream)
        client.send(response)

@packet_handler(1)
def ping(packet: Packet, client: socket, address):
    logger = logging.getLogger(f'Packet ({packet.id} s{packet.size} by {address})')
    logger.debug(f"ping: {packet.id} sized {packet.size} by {address}")

    long = packet.stream.read(8)
    tosend = b''.join([bytes([len(long)+1, 0x01]), long])
    logger.debug(f'pong: {tosend}')
    client.send(tosend)

def handle_legacy_ping(logger, stream: BufferedIOBase):
        # handle legacy ping
        legacyid = stream.read(1)[0]
        if legacyid != 0xfa:
            logger.warning(f'received invalid legacy packet identifier {hex(legacyid)}')
        logger.debug('valid legacy packet')
        strlen = int.from_bytes(stream.read(2))
        pinghost = stream.read(strlen*2).decode('utf-16be')
        logger.info(f'legacy packet: "{pinghost}"')
        strlen = int.from_bytes(stream.read(2))
        proto = stream.read(1)[0]
        logger.info(f'legacy protocol: {proto}')
        strlen = int.from_bytes(stream.read(2))
        hostname = stream.read(strlen*2).decode('utf-16be')
        port = int.from_bytes(stream.read(4))
        logger.info(f'legacy connecting to {hostname}:{port}')
        msg = '§1\x00' # string header
        version = environ.get('mcversion', 'Any version')
        maxp = int(environ.get('mcmaxplr', '50'))
        onlp = int(environ.get('mconlineplr', '100'))
        motd = environ.get('mcmotd', '§da fake status server')
        proto = environ.get('mcproto', 'same')
        if proto == 'same':
            protocol = proto
        else:
            protocol = int(proto)
        msg += f'{str(protocol)}\x00{version}\x00{motd}\x00{str(onlp)}\x00{str(maxp)}\x00'
        msg = msg.encode('utf-16be')
        lngt = (len(msg)//2).to_bytes(2)
        packet = b'\xff' + lngt
        response = b''.join([packet, msg])
        logger.debug(f'responding with {response}')
        return response

@unsized_packet_handler(254)
def legacy_ping(size: int, client: socket, address, stream):
    logger = logging.getLogger(f'Packet (legacy s{size} by {address})')
    logger.info(f'legacy ping: {size} {address}')
    
    response = handle_legacy_ping(logger, stream)
    client.send(response)
    client.close()
    return True

class ReceivePacketServer(TCPServer):
    def __init__(self, server_address: tuple[str | bytes | bytearray, int] | tuple[str | bytes | bytearray, int, int, int], RequestHandlerClass, bind_and_activate: bool = True) -> None:
        self.logger = logging.getLogger('PacketServer')
        self.logger.info(f'Starting server...')
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
    def finish_request(self, request, client_address) -> None:
        self.logger.info(f'Connected: {client_address}')
        super().finish_request(request, client_address)
        self.logger.info(f'DISconnected: {client_address}')
        handshake_data.pop(client_address, None)

def main():
    from sys import argv
    logger = logging.getLogger('main')
    port = 8500
    if(len(argv) > 1):
        port = int(argv[1])
    addr = environ.get('mcaddr', 'localhost')
    address = (addr, port)
    global servericon
    try:
        img = Image.open(environ.get('mcicon', 'icon.png')).resize((64, 64), Image.Resampling.BILINEAR)
        buff = BytesIO()
        img.save(buff, format='PNG')
        servericon = base64.b64encode(buff.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f'Couldn\'t open icon.png: {type(e)}')
        print(traceback.print_exc())
        servericon = ''
    server = ReceivePacketServer(address, PacketServerHandler, True)
    server.serve_forever()

if __name__ == '__main__':
    main()
