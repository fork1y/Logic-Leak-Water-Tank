"""Minimal fakes of the pymodbus datastore classes used by modbus_server."""


class ModbusSequentialDataBlock:
    def __init__(self, address, values):
        self.address = address
        self.values = list(values)

    def getValues(self, address, count=1):  # noqa: N802
        return self.values[address:address + count]

    def setValues(self, address, values):  # noqa: N802
        for i, v in enumerate(values):
            self.values[address + i] = v


class ModbusSlaveContext:
    def __init__(self, di=None, co=None, ir=None, hr=None, zero_mode=False):
        self.di = di
        self.co = co
        self.ir = ir
        self.hr = hr
        self.zero_mode = zero_mode


class ModbusServerContext:
    def __init__(self, slaves=None, single=True):
        self.slaves = slaves
        self.single = single
