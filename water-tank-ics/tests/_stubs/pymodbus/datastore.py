"""Fake datastore classes mirroring the pymodbus 3.x API we rely on."""


class ModbusSequentialDataBlock:
    def __init__(self, address, values):
        self.address = address
        self.values = list(values)

    def getValues(self, address, count=1):
        return self.values[address:address + count]

    def setValues(self, address, values):
        for i, v in enumerate(values):
            self.values[address + i] = v


class ModbusSlaveContext:
    def __init__(self, di=None, co=None, ir=None, hr=None, zero_mode=False):
        self.di, self.co, self.ir, self.hr = di, co, ir, hr
        self.zero_mode = zero_mode


class ModbusServerContext:
    def __init__(self, slaves=None, single=True):
        self.slaves = slaves
        self.single = single
