import ctypes
import snap7
from snap7.util import set_bool, get_bool, set_real

class S7Server:
    def __init__(self):
        # Initialize the Snap7 Server
        self.server = snap7.server.Server()
        self.db_number = 1
        # Create a 100-byte memory block for DB1
        self.data = bytearray(100) 
        
        userdata = (ctypes.c_byte * len(self.data)).from_buffer(self.data)
        self.server.register_area(snap7.type.SrvArea.DB, self.db_number, userdata)

    def start(self):
        self.server.start()
        print("[*] Siemens S7 Server running on 0.0.0.0:102 (DB1 Active)")

    def get_commands(self):
        """
        Byte 0: 
        Bit 0 = Inlet Command
        Bit 1 = Outlet Command
        Bit 2 = Blower Command
        """
        inlet_cmd = get_bool(self.data, 0, 0)
        outlet_cmd = get_bool(self.data, 0, 1)
        blower_cmd = get_bool(self.data, 0, 2)
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
        """
        Writes the current PLC state into the S7 Data Block (DB1).
        """
        # Boolean Status at Byte 0
        set_bool(self.data, 0, 0, in_s)
        set_bool(self.data, 0, 1, out_s)
        set_bool(self.data, 0, 2, blower_s)
        
        set_real(self.data, 4, float(level))    # DB1.DBD4
        set_real(self.data, 8, float(pressure)) # DB1.DBD8
        set_real(self.data, 12, float(temp))    # DB1.DBD12

        # Extended sewage-treatment telemetry.
        if eq_pct is not None:
            set_real(self.data, 16, float(eq_pct))   # DB1.DBD16
        if aer_pct is not None:
            set_real(self.data, 20, float(aer_pct))  # DB1.DBD20
        if clar_pct is not None:
            set_real(self.data, 24, float(clar_pct)) # DB1.DBD24
        if do_mg_l is not None:
            set_real(self.data, 28, float(do_mg_l))  # DB1.DBD28
        if turbidity is not None:
            set_real(self.data, 32, float(turbidity)) # DB1.DBD32
        if ph is not None:
            set_real(self.data, 36, float(ph))       # DB1.DBD36
        if phase_id is not None:
            set_real(self.data, 40, float(phase_id)) # DB1.DBD40

    def stop(self):
        self.server.stop()