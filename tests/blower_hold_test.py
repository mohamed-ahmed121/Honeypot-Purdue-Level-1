import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.physics import WaterTankPhysics


tank = WaterTankPhysics()
tank.eq_level = 3.0
tank.aer_level = 3.8
tank.clar_level = 1.0

blower_cmd = True
blower_ok_since = None
now = 0.0
DT = 1.0
TARGET_DO = 2.5
TARGET_TURB = 25.0
HOLD = 30.0

for i in range(0, 60):
    state = tank.calculate_step(DT, False, False, blower_cmd)
    now += DT
    ok_do = state['do'] >= TARGET_DO
    ok_turb = state['turb'] <= TARGET_TURB
    if blower_cmd:
        if ok_do and ok_turb:
            if blower_ok_since is None:
                blower_ok_since = now
                print(f"t={now}s: targets reached (DO={state['do']:.2f},Turb={state['turb']:.1f}), starting hold")
            elif (now - blower_ok_since) >= HOLD:
                print(f"t={now}s: targets sustained {HOLD}s -> turning blower OFF")
                blower_cmd = False
                blower_ok_since = None
        else:
            if blower_ok_since is not None:
                print(f"t={now}s: targets lost, resetting hold (DO={state['do']:.2f},Turb={state['turb']:.1f})")
            blower_ok_since = None
    else:
        # blower already off
        pass
    if i % 5 == 0:
        print(f"t={now}s status DO={state['do']:.2f} Turb={state['turb']:.1f} Blower={blower_cmd}")
