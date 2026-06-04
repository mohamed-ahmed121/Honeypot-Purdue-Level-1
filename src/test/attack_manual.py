# Simulates a skilled human attacker probing causal logic

from pymodbus.client import ModbusTcpClient
import time, datetime
import sys

TARGET = "127.0.0.1"
PORT = 5020

def log(msg):
    print(f"[{datetime.datetime.now().isoformat()}] {msg}")
    sys.stdout.flush()

def read_telemetry(client):
    regs = client.read_holding_registers(address=10, count=6).registers
    eq_pct  = regs[0]
    aer_pct = regs[1]
    clar_pct= regs[2]
    do_val  = regs[3] / 100.0
    turb    = regs[4] / 100.0
    ph      = regs[5] / 100.0
    log(f"EQ={eq_pct}% | AER={aer_pct}% | CLAR={clar_pct}% | DO={do_val} | Turb={turb} | pH={ph}")

client = ModbusTcpClient(TARGET, port=PORT, timeout=5)
connected = client.connect()
if not connected:
    log(f"ERROR: Failed to connect to {TARGET}:{PORT}")
    log("Make sure the Modbus server is running (e.g., python control_panel.py or docker-compose up)")
    sys.exit(1)
log("Connected — beginning adversarial interaction")

# Step 1: Baseline read
log("=== STEP 1: Baseline telemetry ===")
read_telemetry(client)

# Step 2: Test causal logic turn blower ON and observe DO increase
log("=== STEP 2: Activate blower — expect DO to rise ===")
client.write_register(address=5, value=1)  # HR5 = blower ON
time.sleep(5)
read_telemetry(client)

# Step 3: Try illegal discharge expect block
log("=== STEP 3: Attempt discharge before quality met ===")
client.write_register(address=2, value=1)  # HR2 = outlet ON
time.sleep(2)
read_telemetry(client)

# Step 4: Disable blower expect DO to drop, turbidity to rise
log("=== STEP 4: Disable blower — expect DO drop ===")
client.write_register(address=5, value=0)
time.sleep(5)
read_telemetry(client)

# Step 5: Try to flood EQ tank past 70% safety limit
log("=== STEP 5: Force inlet — expect auto-shutoff at 70% ===")
client.write_register(address=1, value=1)  # HR1 = inlet ON
time.sleep(10)
read_telemetry(client)

log("Session complete check honeypot logs for dwell time and safety violations")
client.close()