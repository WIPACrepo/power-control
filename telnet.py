#
# Telnet wrapper class that provides a simplified
# telnetlib interface either for telnetlib3 or the
# original telnetlib
#
import asyncio

try:
    import telnetlib3
    _has_telnetlib3 = True
except ImportError:
    import telnetlib
    _has_telnetlib3 = False

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


class AsyncTelnetWrapper(BaseTelnetWrapper):
    def __init__(self, host=None, port=23, **kwargs):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self.reader = None
        self.writer = None
        if host:
            self.open(host, port, **kwargs)

    def open(self, host, port=23, **kwargs):
        async def _open():
            return await telnetlib3.open_connection(host, port, **kwargs)
        self.reader, self.writer = self._loop.run_until_complete(_open())

    def read_until(self, expected, timeout=None):
        async def _read_until():
            return await self.reader.readuntil(expected, timeout)
        return self._loop.run_until_complete(_read_until())

    def read_some(self):
        async def _read():
            return await self.reader.read(1024)
        return self._loop.run_until_complete(_read())

    def read_eager(self):
        async def _read_eager():
            if self.reader._buffer:
                data = self.reader._buffer
                self.reader._buffer = ''
                return data.encode()
            try:
                return (await asyncio.wait_for(self.reader.read(1024), timeout=0)).encode()
            except asyncio.TimeoutError:
                return b''
        return self._loop.run_until_complete(_read_eager())

    def write(self, buffer):
        self.writer.write(buffer.decode() if isinstance(buffer, bytes) else buffer)

    def close(self):
        self.writer.close()
        self._loop.run_until_complete(self.writer.wait_closed())


def TelnetWrapper(host=None, port=23, force_stdlib=False, **kwargs):
    """
    Factory function to get the appropriate Telnet wrapper instance.
    """
    if force_stdlib or not _has_telnetlib3:
        return StdlibTelnetWrapper(host, port, **kwargs)
    return AsyncTelnetWrapper(host, port, **kwargs)
