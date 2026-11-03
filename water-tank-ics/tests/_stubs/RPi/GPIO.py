"""Minimal fake of RPi.GPIO for off-Pi testing.

Tracks the last level driven onto each pin so input() reflects output()/setup
initial, which is all the pump/sensor tests need.
"""
BCM = "BCM"
BOARD = "BOARD"
OUT = "OUT"
IN = "IN"
HIGH = 1
LOW = 0

_levels = {}
_mode = None


def setmode(mode):
    global _mode
    _mode = mode


def setwarnings(flag):
    pass


def setup(pin, mode, initial=None):
    if mode == OUT:
        _levels[pin] = initial if initial is not None else LOW
    else:
        _levels.setdefault(pin, LOW)


def output(pin, level):
    _levels[pin] = level


def input(pin):
    return _levels.get(pin, LOW)


def cleanup(*args):
    _levels.clear()
