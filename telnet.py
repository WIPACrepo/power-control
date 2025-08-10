#
# Telnet wrapper class that provides a simplified
# telnetlib interface either for telnetlib3 or the
# original telnetlib
#
import asyncio

try:
    import telnetlib
    _has_telnetlib = True
except ImportError:
    _has_telnetlib = False

class BaseTelnetWrapper:
    def open(self, host, port=23, **kwargs): raise NotImplementedError
    def read_until(self, expected, timeout=None): raise NotImplementedError
    def read_some(self): raise NotImplementedError
    def read_eager(self): raise NotImplementedError
    def write(self, buffer): raise NotImplementedError
    def close(self): raise NotImplementedError
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()


class StdlibTelnetWrapper(BaseTelnetWrapper):
    def __init__(self, host=None, port=23, **kwargs):
        self._telnet = None
        if host:
            self.open(host, port, **kwargs)

    def open(self, host, port=23, **kwargs):
        self._telnet = telnetlib.Telnet(host, port, **kwargs)

    def read_until(self, expected, timeout=None):
        return self._telnet.read_until(expected, timeout)

    def read_some(self):
        return self._telnet.read_some()

    def read_eager(self):
        return self._telnet.read_eager()

    def write(self, buffer):
        self._telnet.write(buffer)

    def close(self):
        self._telnet.close()

class AsyncRawTelnetWrapper(BaseTelnetWrapper):
    def __init__(self, host=None, port=23, **kwargs):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self.reader = None
        self.writer = None
        if host:
            self.open(host, port, **kwargs)

    def open(self, host, port=23, **kwargs):
        async def _open():
            return await asyncio.open_connection(host, port, **kwargs)
        self.reader, self.writer = self._loop.run_until_complete(_open())

    def read_until(self, expected: bytes, timeout=None) -> bytes:
        async def _read_until():
            buffer = b""
            try:
                while True:
                    chunk = await asyncio.wait_for(self.reader.read(1024), timeout=timeout)
                    if not chunk:
                        # Connection closed
                        break
                    buffer += chunk
                    if expected in buffer:
                        break
                return buffer
            except asyncio.TimeoutError:
                return buffer  # partial data on timeout
        return self._loop.run_until_complete(_read_until())

    def read_some(self, n=1024) -> bytes:
        async def _read_some():
            try:
                data = await asyncio.wait_for(self.reader.read(n), timeout=0.0001)
                return data
            except asyncio.TimeoutError:
                return b""
        return self._loop.run_until_complete(_read_some())

    def read_eager(self) -> bytes:
        """
        Read any bytes immediately available without blocking.
        Returns empty bytes if no data is ready.
        """
        async def _read_eager():
            # First, grab any data already buffered internally
            buf = b""
            if getattr(self.reader, "_buffer", None):
                buf = self.reader._buffer
                self.reader._buffer = b""
            try:
                more = await asyncio.wait_for(self.reader.read(1024), timeout=0.0001)
                buf += more
            except asyncio.TimeoutError:
                pass
            return buf
        return self._loop.run_until_complete(_read_eager())

    def write(self, data: bytes):
        async def _write():
            self.writer.write(data)
            await self.writer.drain()
        self._loop.run_until_complete(_write())

    def close(self):
        self.writer.close()
        self._loop.run_until_complete(self.writer.wait_closed())

def TelnetWrapper(host=None, port=23, force_stdlib=False, **kwargs):
    """
    Factory function to get the appropriate Telnet wrapper instance.
    """
    if _has_telnetlib:
        return StdlibTelnetWrapper(host, port, **kwargs)
    return AsyncRawTelnetWrapper(host, port, **kwargs)
