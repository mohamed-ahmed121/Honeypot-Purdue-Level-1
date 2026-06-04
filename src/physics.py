import math
import random

class WaterTankPhysics:
    def __init__(self, radius=1.0, max_height=5.0, pipe_radius=0.12):
        self.radius = radius
        self.max_height = max_height
        self.pipe_area = math.pi * (pipe_radius ** 2)
        self.tank_area = math.pi * (radius ** 2)
        self.gravity = 9.81

        # Three-stage wastewater process levels (m).
        self.eq_level = 1.2
        self.aer_level = 1.0
        self.clar_level = 0.8

        self.current_height = self.clar_level
        self.temperature = 24.0

        self.ambient_temp = 24.0
        self.inflow_rate = 0.10
        self.transfer_rate = 0.07
        self.outflow_rate = 0.09

        # Simplified wastewater quality variables
        # Low DO, high turbidity, acidic pH are typical of untreated wastewater.
        self.do_mg_l = 0.4
        self.turbidity_ntu = 55.0
        self.ph = 5.9
        self.phase_id = 0
        self.phase_name = "equalization"

    def _update_phase(self, inlet_open, outlet_open, blower_on):
        eq_pct = (self.eq_level / self.max_height) * 100
        aer_pct = (self.aer_level / self.max_height) * 100
        clar_pct = (self.clar_level / self.max_height) * 100
        # If the blower is on the process should be in aeration
        if blower_on:
            self.phase_id = 2
            self.phase_name = "aeration"
            return

        # Prefer progression toward clarification: check clarifier and aeration
        # levels first so that turning the blower OFF after aeration doesn't
        # immediately revert the process back to equalization just because
        # the equalization tank is below its threshold.
        if clar_pct >= 70.0:
            self.phase_id = 4
            self.phase_name = "discharge"
        elif aer_pct >= 70.0:
            # When aeration volume is high enough, transition toward clarification
            if clar_pct < 70.0:
                self.phase_id = 3
                self.phase_name = "transfer_to_clarification"
            else:
                self.phase_id = 3
                self.phase_name = "clarification"
        elif eq_pct >= 70.0:
            self.phase_id = 1
            self.phase_name = "transfer_to_aeration"
        else:
            self.phase_id = 0
            self.phase_name = "equalization"

    def calculate_step(self, dt, inlet_open, outlet_open, blower_on):
        # Commands are mapped as: inlet_open=influent pump, outlet_open=effluent pump,
        # blower_on=blower for aeration.
        self._update_phase(inlet_open, outlet_open, blower_on)

        q_in = self.inflow_rate if inlet_open else 0.0
        q_eq_to_aer = self.transfer_rate if self.eq_level > 0.40 else 0.0
        q_aer_to_clar = self.transfer_rate * 0.95 if self.aer_level > 0.35 else 0.0
        q_out = self.outflow_rate if outlet_open and self.clar_level > 0.25 else 0.0

        if self.phase_id == 0:
            q_eq_to_aer *= 0.25
            q_aer_to_clar *= 0.10
        elif self.phase_id == 1:
            q_eq_to_aer *= 1.50
            q_aer_to_clar *= 0.35
        elif self.phase_id == 2:
            q_eq_to_aer *= 0.85
            q_aer_to_clar *= 1.10
        elif self.phase_id == 3:
            q_eq_to_aer *= 0.20
            q_aer_to_clar *= 0.85
            q_out *= 0.15
        elif self.phase_id == 4:
            q_eq_to_aer *= 0.05
            q_aer_to_clar *= 0.40
            q_out *= 1.40

        self.eq_level += ((q_in - q_eq_to_aer) / self.tank_area) * dt
        self.aer_level += ((q_eq_to_aer - q_aer_to_clar) / self.tank_area) * dt
        self.clar_level += ((q_aer_to_clar - q_out) / self.tank_area) * dt

        self.eq_level = max(0.0, min(self.max_height, self.eq_level))
        self.aer_level = max(0.0, min(self.max_height, self.aer_level))
        self.clar_level = max(0.0, min(self.max_height, self.clar_level))

        # Blower improves oxygen transfer and clarification quality.
        # When blower is onO2 rises faster and turbidity falls faster.
        if blower_on:
            self.do_mg_l += 0.8 * 1.5 * dt  # boost DO rise
            self.turbidity_ntu -= 0.3 * 2.0 * dt  # faster turbidity reduction
        else:
            # process doesn't immediately lose all gains. Use low rates.
            self.do_mg_l -= 0.20 * dt
            self.turbidity_ntu += 0.05 * dt

        # Outlet operation with weak chemical effect.
        if outlet_open:
            self.ph -= 0.01 * dt
        else:
            self.ph += (7.0 - self.ph) * 0.01 * dt

        self.do_mg_l = max(0.3, min(8.5, self.do_mg_l))
        self.turbidity_ntu = max(1.0, min(80.0, self.turbidity_ntu))
        self.ph = max(5.8, min(8.8, self.ph))

        # Keep a slowly drifting process temperature for existing telemetry and alarms.
        if blower_on:
            self.temperature += 0.08 * dt
        else:
            self.temperature += (self.ambient_temp - self.temperature) * 0.02 * dt

        self.current_height = self.clar_level
        pressure_bar = (1000 * self.gravity * self.current_height / 100000)

        return {
            "pct": (self.current_height / self.max_height) * 100,
            "pressure": max(0, pressure_bar + random.uniform(-0.001, 0.001)),
            "temp": self.temperature + random.uniform(-0.05, 0.05),
            "eq_pct": (self.eq_level / self.max_height) * 100,
            "aer_pct": (self.aer_level / self.max_height) * 100,
            "clar_pct": (self.clar_level / self.max_height) * 100,
            "do": self.do_mg_l + random.uniform(-0.03, 0.03),
            "turb": self.turbidity_ntu + random.uniform(-0.2, 0.2),
            "ph": self.ph + random.uniform(-0.02, 0.02),
            "phase_id": self.phase_id,
            "phase": self.phase_name
        }