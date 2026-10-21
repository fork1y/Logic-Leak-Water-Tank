"""Fake RPi.GPIO for off-Pi testing. Records pin writes; no real hardware."""
BCM = "BCM"; BOARD = "BOARD"; OUT = "OUT"; IN = "IN"; HIGH = 1; LOW = 0

_state = {"mode": None, "levels": {}, "setup": {}}

def setmode(m): _state["mode"] = m
def setwarnings(_): pass
def setup(pin, direction, initial=None):
    _state["setup"][pin] = direction
    if initial is not None:
        _state["levels"][pin] = initial
def output(pin, level): _state["levels"][pin] = level
def input(pin): return _state["levels"].get(pin, LOW)
def cleanup(): _state["levels"].clear()
