import traceback
import socketserver
from socket import socket
import varint
from io import BytesIO, BufferedIOBase
import logging

logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')

all_packets = {}
all_unsized_packets = {}

def _packet_decorator_factory():
    registry = {}
    def _packet_decorator(packid):
        def _register_packet(func, *args, **kwargs):
            all_packets[packid] = func
            return func
        return _register_packet
    return _packet_decorator

def _unsized_packet_decorator_factory():
    def _unsized_packet_decorator(packid):
        def _register_upacket(func):
            all_unsized_packets[packid] = func
            return func
        return _register_upacket
    return _unsized_packet_decorator

packet_handler = _packet_decorator_factory()
unsized_packet_handler = _unsized_packet_decorator_factory()

def read_total_from_stream(stream: BufferedIOBase, n: int):
    readed = 0
    allread = []
    try:
        while(readed < n):
            bytes = stream.read(n - readed)
            allread.append(bytes)
            readed += len(bytes)
    except Exception as e:
        print(f'Exception reading {readed}/{n}')
        print(traceback.format_exc())
    return b''.join(allread)

class Packet:
    def __init__(self, id: int, size: int, stream: BufferedIOBase) -> None:
        self.id = id
        self.size = size
        self.stream = stream
        pass

class PacketServerHandler(socketserver.BaseRequestHandler):
    def __init__(self, request: socket | tuple[bytes, socket], client_address, server: socketserver.BaseServer, timeout = 10) -> None:
        self.logger = logging.getLogger(f'PacketHandler {client_address}')
        if isinstance(request, tuple):
            request = request[1]
        request.settimeout(timeout)
        self.stream = request.makefile('rb')
        super().__init__(request, client_address, server)
    def handle(self) -> None:
        try:
            while True:
                packet_size = varint.decode_stream(self.stream)
                self.logger.debug(f'Got packet sized {packet_size}')
                if packet_size in all_unsized_packets:
                    self.logger.debug(f'{packet_size} is unsized packet')
                    res = all_unsized_packets[packet_size](packet_size, self.request, self.client_address, self.stream)
                    if res == True:
                        continue
                self.logger.debug(f'Not unsized packet, continuing...')
                packet_buffer = read_total_from_stream(self.stream, packet_size)
                packet_stream = BytesIO(packet_buffer)
                packet_id = varint.decode_stream(packet_stream)
                self.logger.debug(f'Packet ID: {packet_id}')
                packet = Packet(packet_id, packet_size, packet_stream)
                if packet_id in all_packets:
                    self.logger.debug('handling...')
                    try:
                        all_packets[packet_id](packet, self.request, self.client_address)
                    except Exception:
                        self.logger.error(f'Exception handling packet {packet_id}')
                        self.logger.error(traceback.print_exc())
                else:
                    self.logger.warning(f'no handler for packet {packet_id}')
        finally:
            return super().handle()