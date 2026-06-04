import sys
import re
import time
import subprocess
from collections import deque
from pymodbus.client import ModbusTcpClient
import snap7
from snap7.util import set_bool, get_bool, get_real


def _show_tank_graph(sample_fn, title):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[!] matplotlib is not installed. Run `pip install -r requirements.txt`.")
        return

    history_seconds = 60.0
    sample_interval = 0.5
    max_points = int(history_seconds / sample_interval)

    timestamps = deque(maxlen=max_points)
    values = {
        "EQ": deque(maxlen=max_points),
        "AER": deque(maxlen=max_points),
        "CLAR": deque(maxlen=max_points),
        "DO": deque(maxlen=max_points),
        "TURB": deque(maxlen=max_points),
        "PH": deque(maxlen=max_points),
    }

    plt.ion()
    fig, axes = plt.subplots(3, 2, sharex=True, figsize=(13, 9))
    axes = axes.flatten()
    fig.canvas.manager.set_window_title(title)

    metrics = [
        ("EQ", "Equalization Tank", "#2563EB", "EQ (%)", 0, 100),
        ("AER", "Aeration Tank", "#059669", "AER (%)", 0, 100),
        ("CLAR", "Clarifier Tank", "#D97706", "CLAR (%)", 0, 100),
        ("DO", "Dissolved Oxygen", "#0F766E", "DO (mg/L)", 0, 10),
        ("TURB", "Turbidity", "#B45309", "NTU", 0, 90),
        ("PH", "pH", "#1D4ED8", "pH", 5.5, 9.0),
    ]

    lines = {}
    for axis, (key, panel_title, color, y_label, y_min, y_max) in zip(axes, metrics):
        line, = axis.plot([], [], color=color, linewidth=2.2)
        lines[key] = line
        axis.set_ylim(y_min, y_max)
        axis.set_ylabel(y_label)
        axis.set_title(panel_title)
        axis.grid(True, alpha=0.25)

    axes[-2].set_xlabel("Time (s)")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(title)
    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    plt.show(block=False)

    start_time = time.time()
    last_quality_log_ts = 0.0

    try:
        while plt.fignum_exists(fig.number):
            sample = sample_fn()
            timestamps.append(sample["timestamp"] - start_time)
            values["EQ"].append(sample["eq_pct"])
            values["AER"].append(sample["aer_pct"])
            values["CLAR"].append(sample["clar_pct"])
            values["DO"].append(sample["do_mg_l"])
            values["TURB"].append(sample["turbidity"])
            values["PH"].append(sample["ph"])

            if timestamps:
                left = max(0.0, timestamps[-1] - history_seconds)
                right = max(history_seconds, timestamps[-1] + sample_interval)

                for axis, (key, _, _, _, y_min, y_max) in zip(axes, metrics):
                    lines[key].set_data(list(timestamps), list(values[key]))
                    axis.set_xlim(left, right)
                    axis.set_ylim(y_min, y_max)

                fig.suptitle(
                    f"{title} | EQ: {sample['eq_pct']:.1f}% | AER: {sample['aer_pct']:.1f}% | "
                    f"CLAR: {sample['clar_pct']:.1f}% | DO: {sample['do_mg_l']:.2f} mg/L | "
                    f"Turb: {sample['turbidity']:.2f} NTU | pH: {sample['ph']:.2f}"
                )
                fig.canvas.draw_idle()
                fig.canvas.flush_events()

                # Emit a concise quality-telemetry log once per second during live monitoring.
                if sample["timestamp"] - last_quality_log_ts >= 1.0:
                    print(
                        f"[Telemetry] DO: {sample['do_mg_l']:.2f} mg/L | "
                        f"Turb: {sample['turbidity']:.2f} NTU | pH: {sample['ph']:.2f}"
                    )
                    last_quality_log_ts = sample["timestamp"]

            plt.pause(sample_interval)
    except KeyboardInterrupt:
        print("\n[*] Tank graph closed.")
    finally:
        plt.ioff()
        plt.close(fig)


def _read_modbus_snapshot(client):
    res = client.read_holding_registers(address=0, count=16)
    if res is None or res.isError():
        raise RuntimeError("Unable to read tank data from Modbus.")

    phase_map = {
        0: "Equalization",
        1: "Transfer to Aeration",
        2: "Aeration",
        3: "Clarification",
        4: "Discharge",
    }

    return {
        "timestamp": time.time(),
        "level": res.registers[0],
        "pressure": res.registers[3] / 100.0,
        "temp": res.registers[4] / 100.0,
        "eq_pct": float(res.registers[10]),
        "aer_pct": float(res.registers[11]),
        "clar_pct": float(res.registers[12]),
        "do_mg_l": res.registers[13] / 100.0,
        "turbidity": res.registers[14] / 100.0,
        "ph": res.registers[15] / 100.0,
        "phase": phase_map.get(res.registers[6], "Unknown"),
    }


def _read_s7_snapshot(s7_client):
    data = s7_client.db_read(1, 0, 44)

    inlet = get_bool(data, 0, 0)
    outlet = get_bool(data, 0, 1)
    blower = get_bool(data, 0, 2)
    level = get_real(data, 4)
    pressure = get_real(data, 8)
    temp = get_real(data, 12)
    eq_pct = get_real(data, 16)
    aer_pct = get_real(data, 20)
    clar_pct = get_real(data, 24)
    do_mg_l = get_real(data, 28)
    turbidity = get_real(data, 32)
    ph = get_real(data, 36)
    phase_id = int(round(get_real(data, 40)))
    phase_map = {
        0: "Equalization",
        1: "Transfer to Aeration",
        2: "Aeration",
        3: "Clarification",
        4: "Discharge",
    }

    return {
        "timestamp": time.time(),
        "inlet": inlet,
        "outlet": outlet,
        "blower": blower,
        "level": level,
        "pressure": pressure,
        "temp": temp,
        "eq_pct": eq_pct,
        "aer_pct": aer_pct,
        "clar_pct": clar_pct,
        "do_mg_l": do_mg_l,
        "turbidity": turbidity,
        "ph": ph,
        "phase": phase_map.get(phase_id, "Unknown"),
    }

def run_dnp3_in_container(raw_input, container_name="guc_honeypot_plc"):
    cmd = [
        "docker",
        "exec",
        "-i",
        container_name,
        "python",
        "/app/control_panel.py",
        raw_input,
    ]

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"[!] Docker exec failed (exit {result.returncode}).")
    except FileNotFoundError:
        print("[!] Docker CLI not found. Install Docker Desktop or run inside the container.")
    except Exception as exc:
        print(f"[!] Failed to run DNP3 in container: {exc}")


def execute_command(device, target, action, protocol):
    if protocol.lower() == "modbus":
        # Connect to the PLC container
        client = ModbusTcpClient('127.0.0.1', port=5020)
        if not client.connect():
            print("[!] Connection Error: Is the Docker container running?")
            return

        # --- 1. READ LOGIC ---
        if action.lower() == "read":
            res = client.read_holding_registers(address=0, count=16)
            if target.lower() == "pressure":
                print(f"[Modbus] Pressure: {res.registers[3] / 100.0:.3f} bar")
            elif target.lower() == "temperature":
                print(f"[Modbus] Temperature: {res.registers[4] / 100.0:.2f} °C")
            elif target.lower() == "all":
                print("[*] Opening live Modbus graph. Close the window to stop monitoring.")
                _show_tank_graph(lambda: _read_modbus_snapshot(client), "Modbus Tank Levels")
            else:
                phase_map = {
                    0: "Equalization",
                    1: "Transfer to Aeration",
                    2: "Aeration",
                    3: "Clarification",
                    4: "Discharge",
                }
                print(f"--- Tank Status ---")
                print(f"Level: {res.registers[0]}% | P: {res.registers[3]/100.0:.3f}b | T: {res.registers[4]/100.0:.2f}C")
                print(f"Inlet: {'ON' if res.registers[1]==1 else 'OFF'} | Outlet: {'ON' if res.registers[2]==1 else 'OFF'} | Blower: {'ON' if res.registers[5]==1 else 'OFF'}")
                print(f"Phase: {phase_map.get(res.registers[6], 'Unknown')}")
                print("--- Sewage Telemetry ---")
                print(
                    f"EQ: {res.registers[10]}% | AER: {res.registers[11]}% | "
                    f"CLAR: {res.registers[12]}% | DO: {res.registers[13]/100.0:.2f} mg/L"
                )
                print(f"Turbidity: {res.registers[14]/100.0:.2f} NTU | pH: {res.registers[15]/100.0:.2f}")

        # --- 2. BLOWER LOGIC (Address 5) ---
        elif device.lower() in ("heater", "blower"):
            # For blower(on, modbus), 'target' is the command (on/off)
            val = 1 if target.lower() == "on" else 0
            client.write_register(address=5, value=val)
            print(f"[*] Sent: Blower -> {target.upper()} (Register 5)")

        # --- 3. VALVE/PUMP LOGIC (Address 1 or 2) ---
        else:
            # For valve(inlet on, modbus), 'target' is inlet/outlet, 'action' is on/off
            addr = 1 if target.lower() == "inlet" else 2
            val = 1 if action.lower() == "on" else 0
            client.write_register(address=addr, value=val)
            print(f"[*] Sent: {target.upper()} -> {action.upper()} (Register {addr})")
            
        client.close()

    elif protocol.lower() == "s7":
        s7_client = snap7.client.Client()
        try:
            s7_client.connect('127.0.0.1', 0, 1) # IP, Rack, Slot
        except Exception as e:
            print(f"[!] S7 Connection Error: {e}")
            return
            
        # --- S7 READ LOGIC ---
        if action.lower() == "read":
            snapshot = _read_s7_snapshot(s7_client)
            if target.lower() == "pressure":
                print(f"[S7] Pressure: {snapshot['pressure']:.3f} bar")
            elif target.lower() == "temperature":
                print(f"[S7] Temperature: {snapshot['temp']:.2f} °C")
            elif target.lower() == "all":
                print("[*] Opening live S7 graph. Close the window to stop monitoring.")
                _show_tank_graph(lambda: _read_s7_snapshot(s7_client), "S7 Tank Levels")
            else:
                print(f"--- Tank Status ---")
                print(f"Level: {snapshot['level']:.1f}% | P: {snapshot['pressure']:.3f}b | T: {snapshot['temp']:.2f}C")
                print(f"Inlet: {'ON' if snapshot['inlet'] else 'OFF'} | Outlet: {'ON' if snapshot['outlet'] else 'OFF'} | Blower: {'ON' if snapshot['blower'] else 'OFF'}")
                print(f"Phase: {snapshot['phase']}")
                print("--- Sewage Telemetry ---")
                print(
                    f"EQ: {snapshot['eq_pct']:.1f}% | AER: {snapshot['aer_pct']:.1f}% | "
                    f"CLAR: {snapshot['clar_pct']:.1f}% | DO: {snapshot['do_mg_l']:.2f} mg/L"
                )
                print(f"Turbidity: {snapshot['turbidity']:.2f} NTU | pH: {snapshot['ph']:.2f}")

        # --- S7 BLOWER LOGIC (DB1, DBX0.2) ---
        elif device.lower() in ("heater", "blower"):
            data = s7_client.db_read(1, 0, 1) # Read the first byte containing flags
            val = True if target.lower() == "on" else False
            set_bool(data, 0, 2, val) # Modifies bit 2 in the byte array
            s7_client.db_write(1, 0, data) # Write the modified byte back
            print(f"[*] Sent (S7): Blower -> {target.upper()} (DB1.DBX0.2)")

        # --- S7 VALVE/PUMP LOGIC (DB1, DBX0.0 or DBX0.1) ---
        else:
            data = s7_client.db_read(1, 0, 1) # Read the first byte containing flags
            bit_idx = 0 if target.lower() == "inlet" else 1
            val = True if action.lower() == "on" else False
            set_bool(data, 0, bit_idx, val) # Modifies bit 0 or 1
            s7_client.db_write(1, 0, data)
            print(f"[*] Sent (S7): {target.upper()} -> {action.upper()} (DB1.DBX0.{bit_idx})")
            
        s7_client.disconnect()

    elif protocol.lower() == "iec61850":
        try:
            import pyiec61850 as iec
        except Exception as exc:
            print("[!] IEC 61850 libraries not available on this host.")
            print("[!] Run inside the Docker container or install pyiec61850.")
            print(f"[!] Details: {exc}")
            return
            
        # Connect to IEC 61850 server
        con = iec.IedConnection_create()
        error = iec.IedConnection_connect(con, "127.0.0.1", 8102)
        if error != iec.IED_ERROR_OK:
            print(f"[!] IEC 61850 Connection Error: {error}")
            iec.IedConnection_destroy(con)
            return

        if action.lower() in ["on", "off", "write"]:
            # Control commands
            val = True if target.lower() == "on" or action.lower() == "on" else False
            
            if device.lower() in ("heater", "blower"):
                ctl_ref = "water_tankTANK/XSWI1.HeatCtl.ctlVal"
                print(f"[*] Sent (IEC 61850): Blower -> {target.upper()} ({ctl_ref})")
            elif device.lower() == "pump" and target.lower() == "inlet":
                ctl_ref = "water_tankTANK/XSWI1.InletCtl.ctlVal"
                print(f"[*] Sent (IEC 61850): Inlet -> {action.upper()} ({ctl_ref})")
            elif device.lower() == "pump" and target.lower() == "outlet":
                ctl_ref = "water_tankTANK/XSWI1.OutletCtl.ctlVal"
                print(f"[*] Sent (IEC 61850): Outlet -> {action.upper()} ({ctl_ref})")
            else:
                print("[!] Unknown IEC 61850 control command")
                iec.IedConnection_close(con)
                iec.IedConnection_destroy(con)
                return
                
            err = iec.IedConnection_writeBooleanValue(con, ctl_ref, iec.IEC61850_FC_CO, val)
            if err != iec.IED_ERROR_OK:
                print(f"[!] Write error: {err}")

        elif action.lower() == "read":
            # Read measurements
            if target.lower() == "level":
                val_ref = "water_tankTANK/LTMP1.LvlSv.instMag.f"
                val, err = iec.IedConnection_readFloatValue(con, val_ref, iec.IEC61850_FC_MX)
                if err == iec.IED_ERROR_OK:
                    print(f"[IEC 61850] Level: {val:.1f}%")
                else:
                    print(f"[!] Read error: {err}")
            elif target.lower() == "temperature":
                val_ref = "water_tankTANK/LTMP1.TmpSv.instMag.f"
                val, err = iec.IedConnection_readFloatValue(con, val_ref, iec.IEC61850_FC_MX)
                if err == iec.IED_ERROR_OK:
                    print(f"[IEC 61850] Temperature: {val:.1f}°C")
                else:
                    print(f"[!] Read error: {err}")
            elif target.lower() == "pressure":
                val_ref = "water_tankTANK/PPTR1.PrsSv.instMag.f"
                val, err = iec.IedConnection_readFloatValue(con, val_ref, iec.IEC61850_FC_MX)
                if err == iec.IED_ERROR_OK:
                    print(f"[IEC 61850] Pressure: {val:.3f} bar")
                else:
                    print(f"[!] Read error: {err}")
            elif target.lower() == "all":
                lvl_ref = "water_tankTANK/LTMP1.LvlSv.instMag.f"
                tmp_ref = "water_tankTANK/LTMP1.TmpSv.instMag.f"
                prs_ref = "water_tankTANK/PPTR1.PrsSv.instMag.f"
                
                lvl, _ = iec.IedConnection_readFloatValue(con, lvl_ref, iec.IEC61850_FC_MX)
                tmp, _ = iec.IedConnection_readFloatValue(con, tmp_ref, iec.IEC61850_FC_MX)
                prs, _ = iec.IedConnection_readFloatValue(con, prs_ref, iec.IEC61850_FC_MX)
                
                print(f"--- Tank Status ---")
                print(f"Level: {lvl:.1f}% | P: {prs:.3f}b | T: {tmp:.1f}C")
                
                # Read controls
                in_ctl   = "water_tankTANK/XSWI1.InletCtl.ctlVal"
                out_ctl  = "water_tankTANK/XSWI1.OutletCtl.ctlVal"
                heat_ctl = "water_tankTANK/XSWI1.HeatCtl.ctlVal"

                in_val,   _ = iec.IedConnection_readBooleanValue(con, in_ctl,   iec.IEC61850_FC_CO)
                out_val,  _ = iec.IedConnection_readBooleanValue(con, out_ctl,  iec.IEC61850_FC_CO)
                heat_val, _ = iec.IedConnection_readBooleanValue(con, heat_ctl, iec.IEC61850_FC_CO)
                
                print(f"Inlet: {'ON' if in_val else 'OFF'} | Outlet: {'ON' if out_val else 'OFF'} | Heater: {'ON' if heat_val else 'OFF'}")
            
        iec.IedConnection_close(con)
        iec.IedConnection_destroy(con)

    else:
        print(f"[-] Unknown protocol: {protocol}. Supported: modbus, s7, iec61850")

def main():
    if len(sys.argv) < 2:
        print("Usage: python control_panel.py \"device(target action, protocol)\"")
        print("Examples:")
        print("  python control_panel.py \"heater(on, modbus)\"")
        print("  python control_panel.py \"pump(inlet on, s7)\"")
        print("  python control_panel.py \"heater(on, iec61850)\"")
        print("  python control_panel.py \"read(all, modbus)\"  # opens the live tank graph")
        return

    raw_input = sys.argv[1]
    # Regex handles: device(word1, modbus) OR device(word1 word2, modbus)
    pattern = r"(\w+)\((\w+)(?:\s+(\w+))?,\s*(\w+)\)"
    match = re.match(pattern, raw_input)

    if match:
        device, word1, word2, protocol = match.groups()

        if protocol.lower() == "dnp3":
            try:
                from pydnp3 import opendnp3, asiopal, asiodnp3
            except Exception:
                run_dnp3_in_container(raw_input)
                return

        if device.lower() == "read":
            # read(all, s7) / read(all, modbus) -> show the live shared tank graph
            execute_command(device, word1, "read", protocol)
        elif device.lower() in ("heater", "blower"):
            # heater/on or blower/on -> write the blower flag
            execute_command("blower", word1, "write", protocol)
        elif word2:
            # valve(inlet on, modbus) -> device='valve', target='inlet', action='on'
            execute_command(device, word1, word2, protocol)
    else:
        print("[-] Format Error. Use: heater(on, modbus) or valve(inlet on, modbus)")

if __name__ == "__main__":
    main()