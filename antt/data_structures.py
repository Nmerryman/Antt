"""
This file contains data structures and additional helpers needed for network communications
"""
import json
import enum
import random
import socket
import time
import traceback
import pprint

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
0x07 = resend packets
0x08 = done sending message
0x09 = message fully built
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
    
    def __str__(self):
        dtype = self.type
        value = self.value
        data = self.data
        extra = self.extra
        # crop text when it becomes too long
        if isinstance(dtype, str) and len(dtype) > 100:
            dtype = dtype[:100]
        if isinstance(value, str) and len(value) > 100:
            value = value[:100]
        if isinstance(data, str) and len(data) > 100:
            data = data[:100]
        if isinstance(extra, str) and len(extra) > 100:
            extra = extra[:100]
        
        return f"type={dtype}, {value=}, {data=}, {extra=}"

    def __getitem__(self, name: str):
        return self.storage[name.upper()]

    def __eq__(self, other):
        return self.storage == other.storage

    @property
    def type(self):
        return self.storage["TYPE"]

    @type.setter
    def type(self, val):
        self.storage["TYPE"] = val

    @property
    def value(self):
        return self.storage["VALUE"]

    @value.setter
    def value(self, val):
        self.storage["VALUE"] = val

    @property
    def data(self):
        return self.storage["DATA"]

    @data.setter
    def data(self, val):
        self.storage["DATA"] = val

    @property
    def extra(self):
        return self.storage["EXTRA"]

    @extra.setter
    def extra(self, val):
        self.storage["EXTRA"] = val

    def generate(self):
        temp = self.storage.copy()

        # using hex encoding basically 2x the memory size but is fast and safe in a json context
        if isinstance(temp["TYPE"], bytes):
            temp["TYPE"] = temp["TYPE"].hex()
            temp["type bytes"] = True

        if isinstance(temp["VALUE"], bytes):
            temp["VALUE"] = temp["VALUE"].hex()
            temp["value bytes"] = True

        if isinstance(temp["DATA"], bytes):
            temp["DATA"] = temp["DATA"].hex()
            temp["data bytes"] = True

        if isinstance(temp["EXTRA"], bytes):
            temp["EXTRA"] = temp["EXTRA"].hex()
            temp["extra bytes"] = True

        return json.dumps(temp).encode()

    def parse(self, data):
        check = str(data, "utf-8")
        if check == "":
            self.storage = Packet().storage  # use empty default
        else:
            self.storage: dict = json.loads(check)
            if self.storage.get("type bytes", False):
                self.type = bytes.fromhex(self.type)
                del self.storage["type bytes"]

            if self.storage.get("value bytes", False):
                self.value = bytes.fromhex(self.value)
                del self.storage["value bytes"]

            if self.storage.get("data bytes", False):
                self.data = bytes.fromhex(self.data)
                del self.storage["data bytes"]

            if self.storage.get("extra bytes", False):
                self.extra = bytes.fromhex(self.extra)
                del self.storage["extra bytes"]

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
                # We should probably raise an error here instead
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
        if self.type is None or \
            self.id is None or \
            self.part is None or \
            self.total_parts is None or \
            self.data is None:
            raise InvalidData(f"Not all field for Frame are filled in: {type(self.type)}, {type(self.id)}, {type(self.part)}, {type(self.total_parts)}, {type(self.data)}")

        buffer = b''
        buffer += self.type
        buffer += itob_format(self.id, self._id_len)
        buffer += itob_format(self.part, self._msg_part_len)
        buffer += itob_format(self.total_parts, self._msg_part_len)
        buffer += self.data

        return buffer


class FrameGenerator:
    """
    This can raw -> preped byte string -> raw conversions
    We do checks for and split up too large messages here first
    This class is needed for splitting up strings that are too large and to handle ids
    frame shape:
    <header>
    type info       (1)
    full mesage id  (5)
    message part    (5)
    expected parts  (5)
    </header>
    <message>
    data
    </message>
    """
    def __init__(self, buffer_size: int):
        self.buffer_size = buffer_size
        self.id_len = 5
        self.msg_part_len = 5
        self.message_space = self.buffer_size - 1 - self.id_len - 2 * self.msg_part_len  # We probably don't want to hard code the 11
        self.ids_in_use = set()
        self.latest_id = 0  # It would probably be better to randomly generate these
        # We are assuming type info will always be 1 long

    def new_id(self):
        """
        Generate a new id value.
        This should (but dosesn't rn) wrap and remove old values
        """
        new_id = random.randint(0, 99999)

        # This method organizes packets, but requires full restarts to avoid collisions
        new_id = self.latest_id + 1
        while new_id in self.ids_in_use:
            self.latest_id = new_id
            new_id = self.latest_id + 1
        self.latest_id = new_id

        return new_id

    def prep(self, obj: bytes, m_type: bytes = b'\x05') -> list[Frame]:
        """
        This takes the type and whole base object and prepares a list of sendable byte strings
        """
        out = []
        if m_type == b'\x05':  # this means regular data
            buffer = b""
            m_id = self.new_id()
            # Pre-split all the data chunks
            pre_chunks = []
            log_txt(f"starting chunking", "frame prep")
            if "frame prep" in TOPICS:
                timer = time.time()
            index = 0
            while index < len(obj):
                pre_chunks.append(obj[index:index + self.message_space])
                index += self.message_space
            if "frame prep" in TOPICS:
                log_txt(f"{m_id} built {len(pre_chunks)} chunks in {time.time() - timer}s", "frame prep")
                timer = time.time()

            for num_a, a in enumerate(pre_chunks):
                temp_frame = self.frame_template()
                temp_frame.type = m_type
                temp_frame.id = m_id
                temp_frame.part = num_a
                temp_frame.total_parts = len(pre_chunks)
                temp_frame.data = a
                # Do we want to set built as true?
                out.append(temp_frame)
            if "frame prep" in TOPICS:
                log_txt(f"enumerated {m_id} in {time.time() - timer}s", "frame prep")

        return out

    def frame_template(self):
        temp = Frame()
        temp._id_len = self.id_len
        temp._msg_part_len = self.msg_part_len
        return temp


class SocketConnectionUDP(threading.Thread):
    """
    You are _looking at_ the thread. You are putting into and taking out of the thread/socket itself
    I guess this has kinda evolved to try to do tcp things
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
        self.on_message = None  # pass message to callback if set

        self.alive = False
        self.verified_connection = False

        self.connect_try_limit = 100
        self.connect_try_timeout = 2

        self.debug = []  # NEED TO REMOVE LATER

        self.buffer_size = 1024
        self.dest_socket_buffer_size = 40_000  # I think this should be a fair size
        self.dest_socket_buffer_filled = 0
        self.send_buffer = Queue()
        self.awaiting_space = False
        self.pre_parsed = []
        self.building_blocks = {}
        self.send_memory = {}
        self.request_missing_latency = 1
        self.partial_msg_max_count_bytes = int(math.log(self.buffer_size, 256) // 1 + 1)  # Used for splitting up internal messages (unused)
        self.frame_generator = FrameGenerator(self.buffer_size)
        self.todo = Queue()  # What if we built a tdo list on what we need to do. We could even use priority queue. Not in use rn
        self.last_updated: int = None

    def run(self) -> None:
        """
        Starts the mainloop of the thread
        """
        # This will wait until both prove they are connected
        self._setup_socket()

        while self.alive:
            # Fixme we still have a bug where every 40th frame gets dropped
            self.store_incoming()  # may want to call this multiple times to prioritize not losing data

            # Parse all available frames in the partial
            self.distribute_stored()

            # Check all "In progress" messages to see if anything is past it's latency and needs to re-request frames
            current_time = time.time()
            for k, v in self.building_blocks.items():
                if not v["meta"]["done"] and v["meta"]["last update"] + self.request_missing_latency < current_time:
                    log_txt(f"{self.src_port}: found [{k}] is missing frames", "udp run")
                    self.request_missing_frames(k)
                    v["meta"]["last update"] = current_time

            # Send anything that is ready in the send buffer given there is space in dest buffer
            while not self.send_buffer.empty():
                val = self.send_buffer.get()
                if len(val) + self.dest_socket_buffer_filled < self.dest_socket_buffer_size:
                    log_txt(f"{self.src_port}: sending len({len(val)}) {val if len(val) < 100 else f'{val[:20]}...{val[-15:]}'}", "udp run")
                    self.send_bytes(val)
                    self.dest_socket_buffer_filled += len(val)
                    # self.debug.append("send_buffer")
                    # self.debug.append(val)
                    self.send_buffer.task_done()
                else:
                    if not self.awaiting_space:
                        log_txt(f"{self.src_port}: sending awaiting space", "udp run")
                        self.send_bytes(b'\x01')
                        self.awaiting_space = True
                    break

            # Send out any read messages
            for a in self.pop_finished_messages():
                log_txt(f"{self.src_port}: popping finished messages into out_queue", "udp run")
                self.out_queue.put(a)
            # Execute any incoming commands
            # pprint.pprint(self.__dict__)
            while not self.in_queue.empty():
                val = self.in_queue.get()
                log_txt(f"{self.src_port}: reading in_queue input [{val if len(val) < 100 else 'too long'}]", "udp run")
                if isinstance(val, str):
                    if val == "kill":
                        self.alive = False
                        self._shutdown_socket()
                        return
                    self.out_queue.put((val, eval(val)))  # FIXME PROBABLY A MASSIVE SECURITY RISK

                elif isinstance(val, bytes):
                    self.send_msg(val)
                # It's probably better to make as done sooner, but this lets us see when we have parsed the message
                self.in_queue.task_done()
                log_txt(f"{self.src_port}: in_queue emptied", "udp run")

            while self.on_message and not self.out_queue.empty():
                log_txt(f"{self.src_port}: executing on_message callback", "udp run")
                self.on_message(self.out_queue.get())
                self.out_queue.task_done()

            # Check if we need to send a heartbeat
            if time.time() > self.last_action + self.max_no_action_delay:
                log_txt(f"{self.src_port}: sending idle heartbeat", "udp run")
                self.send_heartbeat()
            # time.sleep(.1)

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
        time_limit = self.connect_try_timeout
        limit = self.connect_try_limit
        timeout_len = time_limit / limit
        count = 0
        self.socket.settimeout(timeout_len)
        log_txt(f"Setting up {self.src_port}\n", "verification")
        while count < limit and not self.verified_connection:
            try:
                data = self.socket.recv(self.buffer_size)
                if data == b"\x04":
                    log_txt(f"{self.src_port}: verify confirmed -> marking", "verification")
                    self.verified_connection = True
                elif data == b"\x03":
                    log_txt(f"{self.src_port}: verify requested -> responding", "verification")
                    self.socket.sendto(b"\x04", self.target)
                    self.verified_connection = True
                else:
                    log_txt(f"{self.src_port}: recv {data} instead", "verification")
            except TimeoutError:
                log_txt(f"{self.src_port}: con_error 1; send request", "verification")
                self.socket.sendto(b"\x03", self.target)
                count += 1
            except socket.timeout:
                log_txt(f"{self.src_port}: con_error 2; send request", "verification")
                self.socket.sendto(b"\x03", self.target)
                count += 1
            except ConnectionResetError:
                log_txt(f"{self.src_port}: con_error 3; send request", "verification")
                self.socket.sendto(b"\x03", self.target)
                count += 1
            time.sleep(timeout_len)

        if count == limit:
            log_txt(f"{self.src_port}: Giving up verification", "verification")
            raise ConnectionNoResponse("Failed to verify socket on other side")

        log_txt(f"{self.src_port}: almost done with verification", "verification")
        self.socket.settimeout(0)
        self.socket.setblocking(False)
        self.alive = True
        log_txt(f"{self.src_port}: Done with verification", "verification")

    def _shutdown_socket(self):
        # todo send a kill message/byte because the other side thinks we're still alive
        self.socket.close()

    def distribute_stored(self):
        for a in self.pre_parsed:
            if len(a) == 0:
                continue
            elif a == b'\x00':
                # Not sure if this should be commented out or not
                # This message also means the buffer is empty
                # self.dest_socket_buffer_filled = 0
                pass
            elif a == b"\x02" or a == b"\x04":  # If we care for the acks, we just need to split up this line
                log_txt(f"{self.src_port}: ack/resetting space flag", "udp distribute")
                self.dest_socket_buffer_filled = 0
                self.awaiting_space = False
            elif a == b'\x01':
                self.socket.sendto(b"\x02", self.target)
            elif a == b'\x03':
                self.socket.sendto(b'\04', self.target)
            elif a[0] == 5 or a[0] == 6:  # I guess this op turns it into an int
                temp = self.frame_generator.frame_template()
                temp.parse(a)
                self.incoming_organizer(temp)
            elif a[0] == 9:
                # We can now delete from saved
                done_id = int.from_bytes(a[1:], "big")
                del self.send_memory[done_id]
                log_txt(f"{self.src_port}: del [{done_id}] after completion flag", "udp distribute")
            elif a[0] == 8:
                # Right now we are assuming that nothing will arrive after the \x08
                # This lets us start requesting for missing information as quick as possible before waiting for the latency timeout
                done_id = int.from_bytes(a[1:], "big")
                # FIXME every 40th frame is missing when sending burst of packets
                self.request_missing_frames(done_id)
                log_txt(f"{self.src_port}: Done requesting missing", "udp distribute")
            elif a[0] == 7:
                log_txt(f"{self.src_port}: starting to resend", "udp distribute")
                missing_id = int.from_bytes(a[1: 1 + self.frame_generator.id_len], "big")
                temp = a[1 + self.frame_generator.id_len:]
                parts = []
                while temp:
                    parts.append(int.from_bytes(temp[:self.frame_generator.msg_part_len], "big"))
                    temp = temp[self.frame_generator.msg_part_len:]
                log_txt(f"{self.src_port}: [{missing_id}] will resend {parts}", "udp distribute")
                if missing_id in self.send_memory:
                    for b in parts:
                        self.send_buffer.put(self.send_memory[missing_id][b].generate())

        self.pre_parsed.clear()

    def send_bytes(self, data: bytes):
        # This is the last time we see the bytes
        self.socket.sendto(data, self.target)
        self.last_action = time.time()
        # print(data.decode())

    def send_msg(self, data: bytes):
        """
        We are sending a normal client/content message
        """
        log_txt(f"{self.src_port}: prepping send_msg data", "udp send msg")
        prep = self.frame_generator.prep(data)

        # Add missing dict to send memory (We know at least one frame exists)
        log_txt(f"{self.src_port}: prep send_memory for {prep[0].id}", "udp send msg")
        if prep[0].id not in self.send_memory:
            self.send_memory[prep[0].id] = {"meta": {"len": prep[0].total_parts, "done": False, "last update": 0}}

        log_txt(f"{self.src_port}: putting [{prep[0].id}] into send buffer", "udp send msg")
        for a in prep:
            self.send_buffer.put(a.generate())

            # Add messages to sent memory
            self.send_memory[a.id][a.part] = a

        log_txt(f"{self.src_port}: putting closing remarks into send buffer", "udp send msg")
        self.send_memory[prep[0].id]["meta"]["last update"] = time.time()
        self.send_buffer.put(b"\x08" + itob_format(prep[0].id, self.frame_generator.id_len))

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
        This can be optimized because we use len checking and exceptions
        """
        first = True
        current = 0
        start_len = len(self.pre_parsed)
        while len(self.pre_parsed) > current or first:
            first = False
            try:
                current = len(self.pre_parsed)
                self.pre_parsed.append(self.socket.recv(self.buffer_size))  # I probably need to try for exceptions here; I forgot how non-blocking works
                if len(self.pre_parsed) < 10:
                    # Keep the logging reasonable
                    log_txt(f"{self.src_port}: preparsed -> {self.pre_parsed}", "udp store")
                else:
                    log_txt(f"{self.src_port}: parsed extended (too long already)", "udp store")
            except BlockingIOError:
                pass
            except ConnectionResetError:
                # TODO do we care about this?
                # print("connection reset error")
                # self.alive = False
                pass
        if len(self.pre_parsed) != start_len and not (len(self.pre_parsed) == 1 and self.pre_parsed[0] == b"\x00"):  # We should count this better so that we don't send way too many beats
            self.send_heartbeat()

    def incoming_organizer(self, frame: Frame):
        """
        This is designed to overwrite old packets if the identification is the same
        """
        # Do packet setup
        if frame.id not in self.building_blocks:
            self.building_blocks[frame.id] = {}
            self.building_blocks[frame.id]["meta"] = {"len": frame.total_parts, "done": False, "last update": 0}

        # Don't insert anything if we don't need to
        if self.building_blocks[frame.id]["meta"]["done"]:
            return

        self.building_blocks[frame.id][frame.part] = frame
        self.building_blocks[frame.id]["meta"]["last update"] = time.time()

        if self.building_blocks[frame.id]["meta"]["len"] == len(self.building_blocks[frame.id]) - 1:  # -1 for meta key
            log_txt(f"{self.src_port}: [{frame.id}] detected as done", "udp organizer")
            self.building_blocks[frame.id]["meta"]['done'] = True
            self.send_buffer.put(b"\x09" + itob_format(frame.id, self.frame_generator.id_len))
        self.last_updated = frame.id

    def request_missing_frames(self, id_num: int):
        if id_num in self.building_blocks:
            if self.building_blocks[id_num]["meta"]["done"]:  # Don't request anything if we already have everything
                log_txt(f"{self.src_port}: message marked as done", "udp request missing")
                return
            total_nums = self.building_blocks[id_num]["meta"]["len"]
        else:
            total_nums = 0
        missing = []  # What messages are missing packets
        for a in range(total_nums):
            if a not in self.building_blocks[id_num]:
                missing.append(a)
        log_txt(f"{self.src_port}: [{id_num}] requesting missing {missing}", "udp request missing")

        buffer_space = int((self.buffer_size - (1 + self.frame_generator.id_len)) / self.frame_generator.msg_part_len)
        while missing:
            chunk = missing[:buffer_space]
            missing = missing[buffer_space:]
            temp_b = b"\x07" + itob_format(id_num, self.frame_generator.id_len)
            for a in chunk:
                temp_b += itob_format(a, self.frame_generator.msg_part_len)
            self.send_buffer.put(temp_b)

    def pop_finished_messages(self):
        out = []
        completed_parts = {}
        for k, v in list(self.building_blocks.items()):
            if v['meta']['done'] and len(v) > v['meta']['len']:  # Done and still holding all parts
                log_txt(f"{self.src_port}: {k} is ready for popping", "udp pop messages")
                # buffer = b''
                # for a in range(0, v['meta']['len']):
                #     buffer += v[a].data
                buffer = b"".join([v[a].data for a in range(0, v["meta"]["len"])])
                out.append(buffer)
                log_txt(f"{self.src_port}: popping [{k}] as done", "udp pop messages")
                # fixme we want to delete only the data when done
                completed_parts[k] = {"meta": v['meta']}
                completed_parts[k]['meta']['last update'] = time.time()
                del self.building_blocks[k]

        # Merge the dictionaries
        self.building_blocks = {**self.building_blocks, **completed_parts}

        return out

    def set_buffer_size(self, size: int):
        self.buffer_size = size
        self.frame_generator.buffer_size = size
        return self

    def block_until_verify(self, timeout: int = 2):
        start = time.time()
        while not self.alive or not self.verified_connection:  # It should be fair to wait until alive
            # Maybe change timeout to be based on self.connect_try_timeout
            if time.time() - start > timeout:
                raise TimeoutError("Failed to verify in time.")
            time.sleep(.01)

    def block_until_message(self, timeout: int = 1) -> bytes:
        return self.out_queue.get(timeout=timeout)

    def block_until_shutdown(self, timeout: int = 1):
        start = time.time()
        while not self.in_queue.empty():
            if time.time() - start > timeout:
                raise TimeoutError("Failed to shutdown in time")
            time.sleep(.01)
        self._shutdown_socket()

    def get_message_status(self, m_id: int):
        if m_id in self.building_blocks:
            return self.building_blocks[m_id].keys(), self.building_blocks[m_id]["meta"]
        return None


class SocketConnectionTCP(threading.Thread):
    """
    You are _looking at_ the thread. You are putting into and taking out of the thread/socket itself
    I guess this has kinda evolved to try to do tcp things
    """

    def __init__(self, src_port: int, target: tuple[str, int], in_queue: Queue = None, out_queue: Queue = None, acts_as: str = "client"):
        log_txt(f"{src_port}: start init", "tcp socket setup")
        # What if we could inherit a socket if it already exists?
        super().__init__()
        self.daemon = True  # Self terminating
        # Dest info
        self.src_port = src_port
        self.target = target
        self.acts_as = acts_as
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
        self.last_updated = 0
        self.max_no_action_delay = 20
        # noinspection PyTypeChecker
        self.socket: socket.socket = None
        self.on_message = None  # out_queue message callback
        self.msg_size_len = 5

        self.alive = False
        self.verified_connection = False
        self.buffer_size = 1024
        self.pre_parsed = b""

        self.connect_try_limit = 100
        self.connect_try_timeout = 2
        log_txt(f"{src_port}: end init", "tcp socket setup")

    def run(self) -> None:

        self._setup_socket()
        self.last_action = time.time()
        log_txt(f"{self.src_port}: setup done", "tcp socket run")
        while self.alive:
            log_txt(f"{self.src_port}: storing", "tcp socket run")
            self.store_incoming()

            log_txt(f"{self.src_port}: merging messages", "tcp socket run")
            for a in self.pop_finished_messages():
                self.out_queue.put(a)

            log_txt(f"{self.src_port}: parsing inputs", "tcp socket run")
            while not self.in_queue.empty():
                val = self.in_queue.get()
                self.in_queue.task_done()

                if isinstance(val, str):
                    if val == "kill":
                        log_txt(f"{self.src_port}: starting kill", "tcp socket run")
                        self.alive = False
                        self._shutdown_socket()
                elif isinstance(val, bytes):
                    self.send_msg(val)

            while self.on_message and not self.out_queue.empty():
                log_txt(f"{self.src_port}: callback start", "tcp socket run")
                self.on_message(self.out_queue.get())
                self.out_queue.task_done()
                log_txt(f"{self.src_port}: callback done", "tcp socket run")

            if time.time() > self.last_action + self.max_no_action_delay:
                self.send_heartbeat()

            time.sleep(.01)

        time.sleep(.1)
        self._shutdown_socket()

    def _setup_socket(self):
        log_txt(f"{self.src_port}: setup", "tcp socket setup")
        self.alive = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("", self.src_port))
        if self.acts_as == "client":
            log_txt(f"{self.src_port}: as client", "tcp socket setup")
            count = 0
            tries = self.connect_try_limit
            try_timeout = self.connect_try_timeout
            try_delay = try_timeout / tries
            while count < tries:
                try:
                    self.socket.connect(self.target)
                    break
                except ConnectionResetError:
                    count += 1
                    time.sleep(try_delay)
            self.socket.sendall(b"\x01")
            log_txt(f"{self.src_port}: awaiting response", "tcp socket setup")
            data = self.socket.recv(self.buffer_size)
            if data != b"\x02":
                log_txt(f"{self.src_port}: received incorrect data", "tcp socket setup")
                raise ConnectionIssue("Unable to verify server is correct class")
        else:  # May want to be more precise
            log_txt(f"{self.src_port}: as server", "tcp socket setup")
            self.socket.listen()
            self.socket = self.socket.accept()[0]
            log_txt(f"{self.src_port}: accepted client")
            data = self.socket.recv(self.buffer_size)
            if data != b"\x01":
                raise ConnectionIssue("Unable to verify client is correct class")
            log_txt(f"{self.src_port}: sending response")
            self.socket.sendall(b"\x02")

        log_txt(f"{self.src_port}: Verification done")
        self.socket.settimeout(0.0)
        self.verified_connection = True

    def _shutdown_socket(self):
        self.socket.close()
        self.alive = False

    def send_msg(self, val: bytes, m_type: bytes = b"\x05"):  # 05 has been designated the standard message type byte
        log_txt(f"{self.src_port}: sending message")
        self.socket.setblocking(True)
        self.socket.sendall(m_type)
        self.socket.sendall(len(val).to_bytes(self.msg_size_len, "big"))
        self.socket.sendall(val)
        self.socket.settimeout(0)
        self.last_action = time.time()

    def send_heartbeat(self):
        self.socket.send(b"\x00")
        self.last_action = time.time()

    def store_incoming(self):
        temp_parts = [self.pre_parsed]
        try:
            while True:
                current = len(temp_parts)
                temp_val = self.socket.recv(self.buffer_size)
                if temp_val != "":
                    temp_parts.append(temp_val)
                log_txt(f"{self.src_port}: saved packet -> {temp_val}", "tcp socket store")
                self.last_updated = time.time()
                if len(temp_parts) == current:
                    break
        except socket.timeout:
            pass
        except BlockingIOError:
            pass
        except ConnectionResetError:
            pass
            # self.alive = False  # maybe?
        except Exception as e:
            log_txt(f"{self.src_port}: {e}")
            raise e

        if len(temp_parts) > 1:
            self.pre_parsed = b"".join(temp_parts)
            log_txt(f"{self.src_port}: joining parts -> {self.pre_parsed}", "tcp socket store")

    def pop_finished_messages(self):

        messages = []

        # Remove heartbeats
        h_i = 0
        while len(self.pre_parsed) > h_i and self.pre_parsed[h_i] == 0:
            h_i += 1
        if h_i != 0:
            log_txt(f"{self.src_port}: removing {h_i} heartbeats", "tcp socket pop")
            self.pre_parsed = self.pre_parsed[h_i:]

        while len(self.pre_parsed) > 0:
            if self.pre_parsed[0] == 5:  # Type implies it's a regular message
                # Enough space for the header?
                if len(self.pre_parsed) < 1 + self.msg_size_len:
                    # log_txt(f"{self.src_port}: 1popping {messages}", "tcp socket pop")
                    return messages
                current_len = int.from_bytes(self.pre_parsed[1:1 + self.msg_size_len], "big")
                # Enough data to fulfill size promise?
                if len(self.pre_parsed) - self.msg_size_len - 1 < current_len:
                    # log_txt(f"{self.src_port}: 2popping {messages}", "tcp socket pop")
                    return messages

                debug_val = self.pre_parsed[1 + self.msg_size_len:1 + self.msg_size_len + current_len]
                messages.append(self.pre_parsed[1 + self.msg_size_len:1 + self.msg_size_len + current_len])
                log_txt(f"{self.src_port}: added message of len={len(messages[-1])} to pop")
                # log_txt(f"{self.src_port}: size={self.msg_size_len}, mlen={current_len}, source={self.pre_parsed}, out={debug_val}")
                self.pre_parsed = self.pre_parsed[1 + self.msg_size_len + current_len:]
            else:
                return messages

        return messages

    def block_until_message(self, timeout: int = 1) -> bytes:
        sleep_len = .1
        count = 0
        try:
            while self.out_queue.empty() and count < timeout / sleep_len:
                time.sleep(sleep_len)
                count += 1
            if count == int(timeout / sleep_len):
                log_txt(f"{self.src_port}: block until timed out; queue always empty")
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

    def block_until_verify(self, timeout: int = 2):
        start = time.time()
        while not self.alive or not self.verified_connection:  # It should be fair to assume we're alive too
            # Maybe change timeout value to be based on self.connect_try_timeout
            if time.time() - start > timeout:
                raise TimeoutError("Failed to verify in time.")
            time.sleep(.01)

    def block_until_shutdown(self, timeout: int = 1):
        start = time.time()
        while not self.in_queue.empty():
            # Not sure if clearing the queue in multiple threads can cause race conditions so we'll not abstract it, and just let main thread work on it
            # self.send_msg(self.in_queue.get())
            # self.in_queue.task_done()
            if time.time() - start > timeout:
                raise TimeoutError("Failed to shutdown in time")
            # time.sleep(.01)
        self._shutdown_socket()


def exception_log(args):
    log_txt(pprint.pformat(args))
    log_txt("".join(traceback.format_tb(args.exc_traceback)))
threading.excepthook = exception_log


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
