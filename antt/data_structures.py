"""
This file contains data structures and additional helpers needed for network communications
"""
import json
import enum
import socket
import time
import psutil
import threading
from queue import Queue, Empty
import math
from antt.cust_logging import *




"""
Just for some packet notation:
0x00 = idle keep alive
0x01 = alive? keep alive
0x02 = ack alive keep alive
0x03 = conn only syn
0x04 = conn only ack
0x05 = small + single packet message (currently acts like \x06 and is wrapped as a multi-packet)
0x06 = multi-packet message
"""


# We are assuming entire packet fits in recv size. May need to add proper data buffering/loading otherwise
# It is not super optimised for readability
class Packet:

    def __init__(self, data_type=None, value=None, data=None, extra=None):
        if not data_type:
            data_type = ''
        if not value:
            value = ''
        if not data:
            data = ''
        if not extra:
            extra = ''
        self.storage = {"TYPE": data_type, "VALUE": value, "DATA": data, "EXTRA": extra}
        self.type = data_type
        self.value = value
        self.data = data
        self.extra = extra
    
    def __str__(self):
        type = self.type
        value = self.value
        data = self.data
        extra = self.extra
        # crop text when it becomes too long
        if isinstance(type, str) and len(type) > 100:
            type = type[:100]
        if isinstance(value, str) and len(value) > 100:
            value = value[:100]
        if isinstance(data, str) and len(data) > 100:
            data = data[:100]
        if isinstance(extra, str) and len(extra) > 100:
            extra = extra[:100]
        
        return f"{type=}, {value=}, {data=}, {extra=}"

    def __getitem__(self, name: str):
        return self.storage[name.upper()]

    def __eq__(self, other):
        return self.storage == other.storage

    def load_storage(self):
        self.type = self.storage["TYPE"]
        self.value = self.storage["VALUE"]
        self.data = self.storage["DATA"]
        self.extra = self.storage["EXTRA"]

    def set_value(self, value):
        self.value = value
        self.storage["VALUE"] = value

    def set_type(self, data_type):
        self.type = data_type
        self.storage["TYPE"] = data_type

    def set_data(self, data):
        self.data = data
        self.storage["DATA"] = data

    def set_extra(self, extra):
        self.extra = extra
        self.storage["EXTRA"] = extra

    def generate(self):
        return json.dumps(self.storage).encode()

    def parse(self, data):
        check = str(data, "utf-8")
        if check == "":
            self.storage = Packet().storage  # use empty default
        else:
            self.storage = json.loads(check)

        self.load_storage()
        log_txt(str(data, "utf-8"), "Parse packet")
        return self


class ConnectionIssue(Exception):
    pass


class ConnectionNoResponse(ConnectionIssue):
    pass


class SocketIssue(Exception):
    pass


class InvalidData(Exception):
    pass


def itob_format(number: int, length: int):
    if number > pow(256, length):
        raise OverflowError("Input value is too big for space constrains")
    return number.to_bytes(length, 'big')


class Frame:
    """
    One frame extracted from the stream for future processing
    """
    def __init__(self, data: bytes = None):
        # These are using defaults for my testing
        self._type_len = 1
        self._id_len = 3
        self._msg_part_len = 3
        self.type = None
        self.id = None
        self.part = None
        self.total_parts = None
        self.data = None
        self.built = False

        if data:
            self.parse(data)

    def parse(self, data: bytes):
        """
        Does the magic (if possible)
        (If possible) class will extract one whole frame from the input stream, parse and load them, and return the untouched remainder of the byte string
        """
        data = self._remove_heartbeats(data)
        header_len = self._type_len + self._id_len + 2 * self._msg_part_len
        if len(data) > header_len:
            offset = 0
            self.type = data[:self._type_len]
            offset += self._type_len
            self.id = int.from_bytes(data[offset:offset + self._id_len], 'big')
            offset += self._id_len
            self.part = int.from_bytes(data[offset:offset + self._msg_part_len], 'big')
            offset += self._msg_part_len
            self.total_parts = int.from_bytes(data[offset:offset + self._msg_part_len], 'big')
            offset += self._msg_part_len

            if len(data) < header_len:
                print("Not enough data:", data)  # this is mainly for debugging but I might keep it in
                # THIS COULD CAUSE A BUG LATER IF I DON'T CHECK FOR self.built
                # self.data = data[offset:]
                return data

            self.data = data[offset:]
            self.built = True

            return self.data
        return data

    def generate(self) -> bytes:
        """
        Uses fields to rebuild the raw byte string used to generate this.
        """
        if not all((self.type, self.id, self.part, self.total_parts, self.data)):
            raise InvalidData("Not all field for Frame are filled in")

        buffer = b''
        buffer += self.type
        buffer += itob_format(self.id, self._id_len)
        buffer += itob_format(self.part, self._msg_part_len)
        buffer += itob_format(self.total_parts, self._msg_part_len)

        return buffer

    @staticmethod
    def _remove_heartbeats(data: bytes):
        # I think this can be removed
        index = 0
        while len(data) > index and data[index] == 0:  # 0 because I guess \x00 is not the same
            index += 1

        return data[index:]


class FrameGenerator:
    """
    This can raw -> preped byte string -> raw conversions
    We do checks for and split up too large messages here first
    This class is needed for splitting up strings that are too large and to handle ids
    frame shape:
    <header>
    type info       (1)
    full mesage id  (3)
    message part    (3)
    expected parts  (3)
    message size    (2)
    </header>
    <message>
    data
    </message>
    """
    def __init__(self, buffer_size: int):
        self.buffer_size = buffer_size
        self.message_space = self.buffer_size - 11
        self.id_len = 3
        self.msg_part_len = 3
        self.ids_in_use = set()
        self.latest_id = 0  # It would probably be better to randomly generate these
        # We are assuming type info will always be 1 long

    def new_id(self):
        """
        Generate a new id value.
        This should (but dosesn't rn) wrap and remove old values
        """
        new_id = self.latest_id + 1
        while new_id in self.ids_in_use:
            self.latest_id = new_id
            new_id = self.latest_id + 1
        self.latest_id = new_id
        
        return new_id

    def prep(self, obj: bytes, m_type: bytes = b'\x05') -> list[bytes]:
        """
        This takes the type and whole base object and prepares a list of sendable byte strings
        """
        out = []
        if m_type == b'\x05':  # this means regular data
            buffer = b""
            m_id = self.new_id()
            # Pre-split all the data chunks
            pre_chunks = []
            while obj:
                pre_chunks.append(obj[:self.message_space])
                obj = obj[self.message_space:]

            for num_a, a in enumerate(pre_chunks):
                buffer += m_type                                # type
                buffer += itob_format(m_id, 3)             # id
                buffer += itob_format(num_a, 3)            # part num
                buffer += itob_format(len(pre_chunks), 3)  # total parts
                buffer += a
                # Save and reset buffer
                out.append(buffer)
                buffer = b''

        return out


class SocketConnection(threading.Thread):
    """
    You are _looking at_ the thread. You are putting into and taking out of the thread/socket itself
    """

    def __init__(self, src_port: int, target: tuple[str, int], in_queue: Queue = None, out_queue: Queue = None):
        # What if we could inherit a socket if it already exists?
        super().__init__()
        self.daemon = True  # Self terminating
        # Dest info
        self.src_port = src_port
        self.target = target
        # Init queue objects if needed
        if in_queue:
            self.in_queue = in_queue
        else:
            self.in_queue = Queue()
        if out_queue:
            self.out_queue = out_queue
        else:
            self.out_queue = Queue()

        self.last_action = 0
        self.max_no_action_delay = 20
        self.max_unrequited_love = 3  # We may not care to check if incoming doesn't happen
        # noinspection PyTypeChecker
        self.socket: socket.socket = None

        self.alive = False
        self.verified_connection = False
        self.buffer_size = 1024
        self.pre_parsed = []
        self.building_blocks = {}
        self.send_memory = {}
        self.partial_msg_max_count_bytes = int(math.log(self.buffer_size, 256) // 1 + 1)  # Used for splitting up internal messages
        self.frame_generator = FrameGenerator(self.buffer_size)

    def run(self) -> None:
        """
        Starts the mainloop of the thread
        """
        # This will wait until both prove they are connected
        self._setup_socket()

        while self.alive:
            self.store_incoming()  # may want to call this multiple times to prioritize not losing data

            # Parse all available frames in the partial
            self.distribute_stored()

            # Send out any read messages
            for a in self.pop_finished_messages():
                self.out_queue.put(a)
            # Execute any incoming commands
            # pprint.pprint(self.__dict__)
            while not self.in_queue.empty():
                val = self.in_queue.get()
                self.in_queue.task_done()
                if isinstance(val, str):
                    if val == "kill":
                        self.alive = False
                        self._shutdown_socket()
                        return
                    self.out_queue.put((val, eval(val)))  # FIXME PROBABLY A MASSIVE SECURITY RISK
                elif isinstance(val, bytes):
                    self.send_msg(val)
            # Check if we need to send a heartbeat
            if time.time() > self.last_action + self.max_no_action_delay:
                self.send_heartbeat()
            time.sleep(.1)

        time.sleep(1)
        self._shutdown_socket()
        time.sleep(1)

    def _setup_socket(self):
        """
        Little abstraction/modulation for which was used in testing
        FIXME We have got to use a better flow
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.src_port))
        timeout_len = .1
        time_limit = 2
        limit = int(time_limit / timeout_len)
        count = 0
        self.socket.settimeout(timeout_len)
        log_txt(f"Setting up {self.src_port}\n", "verification")
        while count < limit and not self.verified_connection:
            try:
                data = self.socket.recv(self.buffer_size)
                if data == b"\x04":
                    log_txt(f"{self.src_port}: verify confirmed -> marking\n", "verification")
                    self.verified_connection = True
                elif data == b"\x03":
                    log_txt(f"{self.src_port}: verify requested -> responding\n", "verification")
                    self.socket.sendto(b"\x04", self.target)
                    self.verified_connection = True
                else:
                    log_txt(f"{self.src_port}: recv {data} instead\n", "verification")
            except TimeoutError:
                log_txt(f"{self.src_port}: con_error 1; send request\n", "verification")
                self.socket.sendto(b"\x03", self.target)
                count += 1
            except socket.timeout:
                log_txt(f"{self.src_port}: con_error 2; send request\n", "verification")
                self.socket.sendto(b"\x03", self.target)
                count += 1
            except ConnectionResetError:
                log_txt(f"{self.src_port}: con_error 3; send request\n", "verification")
                self.socket.sendto(b"\x03", self.target)
                count += 1
            time.sleep(timeout_len)

        if count == limit:
            log_txt(f"{self.src_port}: Giving up verification\n", "verification")
            raise ConnectionNoResponse("Failed to verify socket on other side")

        self.socket.settimeout(0)
        self.socket.setblocking(False)
        self.alive = True

    def _shutdown_socket(self):
        self.socket.close()

    def distribute_stored(self):
        for a in self.pre_parsed:
            if len(a) == 0:
                continue
            elif a == b'\x00' or a == b"\x02" or a == b"\x04":  # If we care for the acks, we just need to split up this line
                continue
            elif a == b'\x01':
                self.socket.sendto(b"\x02", self.target)
            elif a == b'\x03':
                self.socket.sendto(b'\04', self.target)
            elif a[0] == 5 or a[0] == 6:  # I guess this op turns it into an int
                temp = Frame(a)
                self.incoming_organizer(temp)

        self.pre_parsed.clear()

    def send_bytes(self, data: bytes):
        self.socket.sendto(data, self.target)
        self.last_action = time.time()
        # print(data.decode())

    def send_msg(self, data: bytes):
        """
        We are sending a normal client/content message
        """
        prep = self.frame_generator.prep(data)
        for a in prep:
            self.send_bytes(a)

    def send_heartbeat(self):
        key = b"\x00"  # first byte = 0 means heartbeat
        self.send_bytes(key)
        self.last_action = time.time()

    @staticmethod
    def prep_packet(packet: Packet):
        val = packet.generate()
        length = len(val)
        byte_size = length.to_bytes((length.bit_length() + 7) // 8, 'big')
        return byte_size + val

    def store_incoming(self):
        """
        No authentication is done here because we assume nat is taking care of it rn
        """
        first = True
        current = 0
        while len(self.pre_parsed) > current or first:
            first = False
            try:
                current = len(self.pre_parsed)
                self.pre_parsed.append(self.socket.recv(self.buffer_size))  # I probably need to try for exceptions here; I forgot how non-blocking works

            except BlockingIOError:
                pass
            except ConnectionResetError:
                # TODO do we care about this?
                # print("connection reset error")
                # self.alive = False
                pass

    def incoming_organizer(self, frame: Frame):
        """
        This is designed to overwrite old packets if the identification is the same
        """
        # Do packet setup
        if frame.id not in self.building_blocks:
            self.building_blocks[frame.id] = {}
            self.building_blocks[frame.id]["meta"] = {"len": frame.total_parts, "done": False, "last update": 0}

        self.building_blocks[frame.id][frame.part] = frame
        self.building_blocks[frame.id]["meta"]["last update"] = time.time()

        if self.building_blocks[frame.id]["meta"]["len"] == len(self.building_blocks[frame.id]) - 1:  # -1 for meta key
            self.building_blocks[frame.id]["meta"]['done'] = True

    def pop_finished_messages(self):
        out = []
        for k, v in list(self.building_blocks.items()):
            if v['meta']['done']:
                buffer = b''
                for a in range(0, v['meta']['len']):
                    buffer += v[a].data
                out.append(buffer)
                del self.building_blocks[k]

        # print(out)
        return out

    def set_buffer_size(self, size: int):
        self.buffer_size = size
        self.frame_generator.buffer_size = size
        return self

    def block_until_verify(self, timeout: int = 1):
        start = time.time()
        while not self.verified_connection:
            if time.time() - start > timeout:
                raise TimeoutError("Failed to verify in time.")
            time.sleep(.01)

    def block_until_message(self, timeout: int = 1) -> bytes:
        sleep_len = .1
        count = 0
        try:
            while self.out_queue.empty() and count < timeout / sleep_len:
                time.sleep(sleep_len)
                count += 1
            if count == int(timeout / sleep_len):
                raise KeyboardInterrupt  # There's probably a better way to do this
        except KeyboardInterrupt:
            self.in_queue.put("kill")
        try:
            temp = self.out_queue.get(timeout=3)  # fixme This is likely what actually kills the thread
            self.out_queue.task_done()
        except Empty:
            print("No messages found? fexme")
            temp = "Nothing"
        return temp

    def block_until_shutdown(self, timeout: int = 1):
        start = time.time()
        while not self.in_queue.empty():
            if time.time() - start > timeout:
                raise TimeoutError("Failed to shutdown in time")
            time.sleep(.01)
        self._shutdown_socket()


class MessageType(enum.IntEnum):
    command = enum.auto()
    text = enum.auto()
    empty = enum.auto()


class Commands(enum.IntEnum):
    greet = enum.auto()
    close = enum.auto()
    exit = enum.auto()
    is_alive = enum.auto()
    request = enum.auto()
    broadcast = enum.auto()
    unblock = enum.auto()


def get_first_port_from(port: int, limit: int = 50000) -> int:
    used_ports = [a.laddr.port for a in psutil.net_connections()]
    while port in used_ports and port <= limit:
        port += 1
    if port == limit:
        raise ValueError("No valid port found")

    return port
