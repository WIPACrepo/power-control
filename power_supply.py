#!/usr/bin/python
#
# Simple network SCPI power supply control
# through telnet.
#

import time
import socket
import telnetlib

class PowerSupplyException(Exception):
    pass

def PowerSupply(hostname, port = None, supply_type = "generic"):
    """
    Power supply factory class. Select power supply
    interface type based on user-specified type string.
    """
    supply_type = supply_type.lower()
    if supply_type == "kepco":
        supply = Kepco
    elif supply_type == "keysight":
        supply = Keysight
    else:
        supply = SCPI
        
    if port is None:
        return supply(hostname)
    else:
        return supply(hostname, port=port)

class SCPI:
    """
    General power supply SCPI interface.
    Uses telnetlib to interface with supply.
    """
    CMD_DELAY_SEC = 0.2

    def __init__(self, hostname, port=None):
        self.hostname = hostname

        # Port is required, but keep it as keyword 
        # to match subclasses
        if port is None:
            raise PowerSupplyException("No port specified for generic supply type!")            
        self.port = port

        try:
            self.telnet = telnetlib.Telnet(hostname, port)
        except ConnectionRefusedError:
            raise PowerSupplyException("Connection to %s:%d refused" % (hostname, port))
        except socket.gaierror:
            raise PowerSupplyException("Hostname %s unknown" % (hostname))
        self._remote_init()
        self._probe()

    def __str__(self):
        return("%s %s" % (self.manufacturer, self.model))

    def cmd(self, scpi_cmd):
        self.telnet.write((scpi_cmd + "\n").encode())
        time.sleep(self.CMD_DELAY_SEC)
        return self.telnet.read_eager().decode().strip()

    def _remote_init(self):
        return

    def _probe(self):        
        resp = self.cmd("*IDN?")
        # Keysight jams both fwvers and hwvers together in fourth field
        (self.manufacturer, self.model, self.serial, self.fwvers) = resp.split(",", 3)
        
    def getCurrent(self):
        return float(self.cmd("MEAS:CURR?"))

    def setCurrent(self, i):
        self.cmd("SOUR:CURR %f" % i)

    def getVoltage(self):
        return float(self.cmd("MEAS:VOLT?"))

    def setVoltage(self, v):
        self.cmd("SOUR:VOLT %f" % v)

    def off(self):
        self.cmd("OUTP OFF")

    def on(self):
        self.cmd("OUTP ON")

    def isOn(self):
        resp = self.cmd("OUTP?")
        return (int(resp) == 1)

    def isOff(self):
        resp = self.cmd("OUTP?")
        return (int(resp) == 0)

# Customization for different vendors

class Kepco(SCPI):
    """
    Kepco KLN power supply family
    """
    DEFAULT_PORT = 5025
    # FIX ME determine this dynamically
    MAX_VOLTAGE = 80
    MAX_CURRENT = 9.5

    def __init__(self, hostname, port=DEFAULT_PORT):
        super().__init__(hostname, port)

    def _remote_init(self):
        # Put unit in remote mode
        # Otherwise it doesn't respond
        self.cmd("SYST:REM")


class Keysight(SCPI):
    """
    Agilent Keysight N5700 power supply family
    """
    DEFAULT_PORT = 5024
    PROMPT = "SCPI>"
    # FIX ME determine dynamically
    MAX_VOLTAGE = 300
    MAX_CURRENT = 2.5

    def __init__(self, hostname, port=DEFAULT_PORT):
        super().__init__(hostname, port)

    def _remote_init(self):
        # Read header and initial prompt
        self.telnet.read_until(self.PROMPT.encode())

    def cmd(self, scpi_cmd):
        self.telnet.write((scpi_cmd + "\n").encode())
        resp = self.telnet.read_until(self.PROMPT.encode()).decode()
        # Response includes newline and prompt, remove them
        resp = resp.split("\n")[0].strip()
        return resp
