import asyncio
import time
from physics import WaterTankPhysics
from modbus_dev import ModbusServer
from s7_dev import S7Server  # Our new Siemens protocol layer

# Discharge gating thresholds (tunable)
MIN_DO_MG_L = 2.5
MAX_TURB_NTU = 25.0
PH_MIN = 6.5
PH_MAX = 8.5
MIN_CLAR_PCT_FOR_DISCHARGE = 25.0
SUSTAIN_SEC_REQUIRED = 8.0
EQ_AUTO_OFF_PCT = 70.0
AER_AUTO_OFF_PCT = 70.0
CLAR_AUTO_DISCHARGE_PCT = 70.0
TARGET_DO_FOR_BLOWER_OFF = 2.5
TARGET_TURB_FOR_BLOWER_OFF = 10.0
BLOWER_HOLD_SECONDS = 30.0

async def plc_cycle(tank, mb_server, s7_server):
    print("[*] PLC Active: Multi-Protocol (Modbus + S7comm) Engine Started.")
    print("[*] Monitoring process level handoffs at 70% and temp (60°C) cutoffs.")
    
    # INITIALIZATION: Define the current state trackers
    current_in = False
    current_out = False
    current_blower = False
    prev_mb_in = prev_mb_out = prev_mb_blower = None
    prev_s7_in = prev_s7_out = prev_s7_blower = None
    last_time = time.time()
    discharge_ok_since = None
    blower_ok_since = None
    
    while True:
        # Calculate Delta Time for the physics engine
        now = time.time()
        dt = now - last_time
        last_time = now

        # 1. READ: Get commands from all protocols
        mb_in, mb_out, mb_blower = mb_server.get_commands()
        s7_in, s7_out, s7_blower = s7_server.get_commands()

        # 2. COMMAND LOGIC: Change-driven arbitration
        if prev_mb_in is None:
            current_in = mb_in or s7_in
            current_out = mb_out or s7_out
            current_blower = mb_blower or s7_blower
        else:
            if mb_in != prev_mb_in:
                current_in = mb_in
            if s7_in != prev_s7_in:
                current_in = s7_in

            if mb_out != prev_mb_out:
                current_out = mb_out
            if s7_out != prev_s7_out:
                current_out = s7_out

            if mb_blower != prev_mb_blower:
                current_blower = mb_blower
            if s7_blower != prev_s7_blower:
                current_blower = s7_blower

        prev_mb_in, prev_mb_out, prev_mb_blower = mb_in, mb_out, mb_blower
        prev_s7_in, prev_s7_out, prev_s7_blower = s7_in, s7_out, s7_blower

        # Bridge trackers to the command variables used in safety/physics
        in_cmd, out_cmd, blower_cmd = current_in, current_out, current_blower

        # 3. SENSE: Get current system values from the physics simulation
        eq_pct = (tank.eq_level / tank.max_height) * 100
        aer_pct = (tank.aer_level / tank.max_height) * 100
        clar_pct = (tank.clar_level / tank.max_height) * 100
        current_temp = tank.temperature

        # 3. SAFETY LOGIC: Force commands to False if they violate safety limits
        if eq_pct >= EQ_AUTO_OFF_PCT and in_cmd:
            print(f"[i] EQ handoff reached ({eq_pct:.1f}%). Stopping influent and transferring to AER.")
            in_cmd = False
            
        if clar_pct <= 10.0 and out_cmd:
            print(f"[!] SAFETY ALERT: Clarifier low ({clar_pct:.1f}%). Stopping effluent.")
            out_cmd = False
            
        if current_temp >= 60.0 and blower_cmd:
            print(f"[!] SAFETY ALERT: High process temp ({current_temp:.1f}°C). Stopping blower command.")
            blower_cmd = False

        # 3b. DISCHARGE GATING: Require quality and clarifier readiness for sustained period
        if out_cmd:
            ok_do = tank.do_mg_l >= MIN_DO_MG_L
            ok_turb = tank.turbidity_ntu <= MAX_TURB_NTU
            ok_ph = (PH_MIN <= tank.ph <= PH_MAX)
            ok_clar = clar_pct >= MIN_CLAR_PCT_FOR_DISCHARGE

            if not (ok_do and ok_turb and ok_ph and ok_clar):
                reasons = []
                if not ok_do:
                    reasons.append(f"DO {tank.do_mg_l:.2f}<{MIN_DO_MG_L}")
                if not ok_turb:
                    reasons.append(f"Turb {tank.turbidity_ntu:.1f}>{MAX_TURB_NTU}")
                if not ok_ph:
                    reasons.append(f"pH {tank.ph:.2f} outside {PH_MIN}-{PH_MAX}")
                if not ok_clar:
                    reasons.append(f"Clar {clar_pct:.1f}%<{MIN_CLAR_PCT_FOR_DISCHARGE}")

                print(f"[!] DISCHARGE BLOCKED: {'; '.join(reasons)}")
                out_cmd = False
                discharge_ok_since = None
            else:
                if discharge_ok_since is None:
                    discharge_ok_since = now
                    print(f"[i] Discharge conditions met; sustaining for {SUSTAIN_SEC_REQUIRED}s before enabling.")
                    out_cmd = False
                elif (now - discharge_ok_since) < SUSTAIN_SEC_REQUIRED:
                    remaining = SUSTAIN_SEC_REQUIRED - (now - discharge_ok_since)
                    print(f"[i] Discharge waiting: {remaining:.1f}s remaining")
                    out_cmd = False
                else:
                    # sustained good: allow discharge
                    pass
        elif clar_pct >= CLAR_AUTO_DISCHARGE_PCT:
            # Auto-start discharge once the clarifier is full enough.
            out_cmd = True
            discharge_ok_since = None

        # 4. PROCESS: Update physics simulation with validated commands
        state = tank.calculate_step(dt, in_cmd, out_cmd, blower_cmd)

        # AUTO-BLOWER: require sustained good DO and turbidity for hold period
        if blower_cmd:
            ok_do = state.get('do', 0.0) >= TARGET_DO_FOR_BLOWER_OFF
            ok_turb = state.get('turb', 999.0) <= TARGET_TURB_FOR_BLOWER_OFF

            if ok_do and ok_turb:
                if blower_ok_since is None:
                    blower_ok_since = now
                    print(f"[i] Blower targets reached; beginning {BLOWER_HOLD_SECONDS:.0f}s hold before auto-OFF.")
                elif (now - blower_ok_since) >= BLOWER_HOLD_SECONDS:
                    print(f"[i] Blower targets sustained for {BLOWER_HOLD_SECONDS:.0f}s; auto-turning blower OFF and moving toward clarification.")
                    blower_cmd = False
                    blower_ok_since = None
                else:
                    remaining = BLOWER_HOLD_SECONDS - (now - blower_ok_since)
                    # Optional: print once per hold start; avoid spamming every loop
                    pass
            else:
                blower_ok_since = None

        # 5. WRITE: Sync the state back to BOTH Modbus and S7 servers
        # This clears any "stuck" bits in the protocol memory
        mb_server.update_registers(
            state['pct'], 
            in_cmd, 
            out_cmd, 
            state['pressure'], 
            state['temp'], 
            blower_cmd,
            eq_pct=state.get('eq_pct'),
            aer_pct=state.get('aer_pct'),
            clar_pct=state.get('clar_pct'),
            do_mg_l=state.get('do'),
            turbidity=state.get('turb'),
            ph=state.get('ph'),
            phase_id=state.get('phase_id'),
        )
        
        s7_server.update_registers(
            state['pct'], 
            in_cmd, 
            out_cmd, 
            state['pressure'], 
            state['temp'], 
            blower_cmd,
            eq_pct=state.get('eq_pct'),
            aer_pct=state.get('aer_pct'),
            clar_pct=state.get('clar_pct'),
            do_mg_l=state.get('do'),
            turbidity=state.get('turb'),
            ph=state.get('ph'),
            phase_id=state.get('phase_id'),
        )

        # Log status every 2 seconds for visibility in Docker
        if int(now) % 2 == 0:
            status = (
                f"Phase: {state['phase']} | EQ: {state['eq_pct']:.1f}% | "
                f"AER: {state['aer_pct']:.1f}% | CLAR: {state['clar_pct']:.1f}%"
            )
            status += f" | In: {in_cmd} | Out: {out_cmd} | Blower: {blower_cmd}"
            status += f" | DO: {state['do']:.2f} mg/L | Turb: {state['turb']:.1f} NTU | pH: {state['ph']:.2f}"
            print(status)

        # 10Hz frequency
        await asyncio.sleep(0.1)

async def main():
    # Initialize the physical tank
    tank = WaterTankPhysics()
    
    # Initialize Modbus server
    mb_server = ModbusServer()
    
    # Initialize and start the S7 server
    s7_server = S7Server()
    s7_server.start()

    # Run the Modbus server and the PLC logic cycle concurrently
    await asyncio.gather(
        mb_server.run(), 
        plc_cycle(tank, mb_server, s7_server)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] PLC Shutdown.")