from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext


class ModbusServer:
    def __init__(self, host="0.0.0.0", port=5020):
        self.host = host
        self.port = port

        # Initialize the memory block and immediately wrap it in the context
        slave_context = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [0] * 32)
        )
        # single=True maps all incoming Modbus TCP traffic to slave ID 0
        self.context = ModbusServerContext(slaves=slave_context, single=True)

    def get_commands(self):
        # Read from the LIVE server memory.
        # 3 = Holding Registers, 1 = Start Address, 5 = Count
        values = self.context[0].getValues(3, 1, 5)

        inlet_cmd = values[0] == 1  # HR1
        outlet_cmd = values[1] == 1  # HR2
        blower_cmd = values[4] == 1  # HR5 (blower)

        return inlet_cmd, outlet_cmd, blower_cmd

    def update_registers(
        self,
        level,
        in_s,
        out_s,
        pressure,
        temp,
        blower_s,
        eq_pct=None,
        aer_pct=None,
        clar_pct=None,
        do_mg_l=None,
        turbidity=None,
        ph=None,
        phase_id=None,
    ):
        # Write to the LIVE server memory.
        self.context[0].setValues(3, 0, [int(level)])  # HR0
        self.context[0].setValues(3, 1, [int(in_s)])  # HR1
        self.context[0].setValues(3, 2, [int(out_s)])  # HR2
        self.context[0].setValues(3, 3, [int(pressure * 100)])  # HR3
        self.context[0].setValues(3, 4, [int(temp * 100)])  # HR4
        self.context[0].setValues(3, 5, [int(blower_s)])  # HR5 (blower)

        # Extended sewage-treatment telemetry (new map, legacy-safe).
        if eq_pct is not None:
            self.context[0].setValues(3, 10, [int(eq_pct)])
        if aer_pct is not None:
            self.context[0].setValues(3, 11, [int(aer_pct)])
        if clar_pct is not None:
            self.context[0].setValues(3, 12, [int(clar_pct)])
        if do_mg_l is not None:
            self.context[0].setValues(3, 13, [int(do_mg_l * 100)])
        if turbidity is not None:
            self.context[0].setValues(3, 14, [int(turbidity * 100)])
        if ph is not None:
            self.context[0].setValues(3, 15, [int(ph * 100)])
        if phase_id is not None:
            self.context[0].setValues(3, 6, [int(phase_id)])

    async def run(self):
        print(f"[*] Modbus Server running on {self.host}:{self.port}")
        await StartAsyncTcpServer(context=self.context, address=(self.host, self.port))