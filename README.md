# Water Treatment Plant Honeypot

A realistic honeypot simulation of an industrial water treatment facility with multi-protocol support (Modbus/TCP, Siemens S7) for security research and attack scenario testing.

## Overview

This project simulates a **three-stage wastewater treatment process**:
1. **Equalization Tank (EQ)** - Initial gathering and settling
2. **Aeration Tank (AER)** - Biological treatment with oxygen injection
3. **Clarification Tank (CLAR)** - Final settling and pH control before discharge

The system models realistic physics (fluid dynamics, chemical processes) and enforces safety constraints to detect anomalies and unauthorized control attempts.

## Features

- ✅ **Multi-Protocol Support**: Modbus/TCP, Siemens S7comm
- ✅ **Realistic Physics Engine**: Simulates tank levels, dissolved oxygen, turbidity, pH
- ✅ **Safety Interlocks**: Prevents unsafe discharge and equipment damage
- ✅ **Attack Simulation Scripts**: Test honeypot responses to malicious commands
- ✅ **Live Monitoring Dashboard**: Real-time visualization of tank states
- ✅ **Docker Support**: Easy containerized deployment

## Quick Start

### Prerequisites

- Python 3.8+
- Docker & Docker Compose

### Installation

1. **Clone and set up virtual environment:**
   ```bash
   cd Honeypot
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Linux/Mac:
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Running the Honeypot

### Option 1: Python

Start the simulation server:
```bash
python src/main.py
```

This starts:
- **Modbus/TCP Server** on port 5020
- **Siemens S7comm** on port 102
- **Physics Engine** updating tank states in real-time

### Option 2: Docker (recommended that is what i used)

```bash
docker-compose up
```

This containerizes the entire honeypot with volume mounting for live code changes.

## Testing & Attack Scenarios

Once the honeypot is running, test it with the attack simulation scripts:

### Automated Scanner (Fast reconnaissance)
```bash
python src/test/attack_scanner.py
```
Simulates automated reconnaissance tool (like Nmap/PLCScan) that:
- Enumerates all 16 holding registers
- Attempts forced discharge
- Verifies if safety systems block the attack

**Output example:**
```
[2026-06-05T01:54:59.858110] Starting attack scanner - connecting to 127.0.0.1:5020
[2026-06-05T01:54:59.865525] Connected to Modbus/TCP on port 5020
[2026-06-05T01:54:59.865686] === PHASE 1: Register Enumeration ===
[2026-06-05T01:54:59.872050] HR0 = 27 (Tank level)
[2026-06-05T01:55:22.888188] === PHASE 2: Forced Discharge Attempt ===
[2026-06-05T01:55:24.891576] HR2 readback = 0 (blocked by safety interlocks)
```

### Manual Attack (Step-by-step adversarial interaction)
```bash
python src/test/attack_manual.py
```
Simulates a skilled attacker probing causal relationships:
- Establishes baseline telemetry
- Activates blower and observes DO (dissolved oxygen) rise
- Attempts discharge before quality standards met
- Forces inlet to trigger auto-shutoff at 70%
- Takes ~25 seconds

**Output example:**
```
[2026-06-05T01:56:49.668982] EQ=7% | AER=20% | CLAR=31% | DO=0.31 | Turb=73.19 | pH=6.95
[2026-06-05T01:56:54.675978] EQ=7% | AER=18% | CLAR=33% | DO=6.24 | Turb=70.27 | pH=6.97
[2026-06-05T01:57:11.691591] Session complete - check honeypot logs for dwell time and safety violations
```

### Live Monitoring Dashboard
```bash
python control_panel.py
```
Displays real-time 6-panel graph of:
- Tank levels (EQ, AER, CLAR)
- Water quality metrics (DO, Turbidity, pH)

Updates every 0.5 seconds for 60-second rolling window.

## Modbus/TCP Register Map

| Register | Name | Purpose | Range |
|----------|------|---------|-------|
| HR0 | EQ_Level | Equalization tank fill % | 0-100 |
| HR1 | Inlet_Cmd | Inlet pump command | 0/1 |
| HR2 | Outlet_Cmd | Discharge outlet command | 0/1 |
| HR3 | AER_Level | Aeration tank fill % | 0-100 |
| HR4 | Temp | Water temperature | 20-40°C |
| HR5 | Blower_Cmd | Blower on/off | 0/1 |
| HR10 | DO | Dissolved oxygen | 0-10 mg/L |
| HR11 | pH | pH value | 0-14 (×100) |
| HR12 | Turbidity | Turbidity | 0-100 NTU |

## Safety Constraints

The honeypot enforces these realistic safety limits:

- **Discharge Gate**: Requires DO ≥ 2.5 mg/L, Turbidity ≤ 25 NTU, pH 6.5-8.5, and sustained 8+ seconds
- **Tank Overflow**: Inlet auto-shutoff at 70% level in equalization and aeration tanks
- **Multi-Protocol Arbitration**: Commands from any protocol (Modbus/S7/IEC) are processed with change-driven logic
- **Unauthorized Discharge Blocking**: Prevents discharge without meeting water quality standards

## Project Structure

```
Honeypot/
├── src/
│   ├── main.py              # Main PLC cycle & multi-protocol engine
│   ├── physics.py           # Water tank physics & quality simulation
│   ├── modbus_dev.py        # Modbus/TCP protocol implementation
│   ├── s7_dev.py            # Siemens S7comm protocol implementation
│   ├── test/
│   │   ├── attack_scanner.py    # Automated reconnaissance tool
│   │   └── attack_manual.py     # Manual adversarial attack simulation
│   └── ...
├── control_panel.py         # Live monitoring dashboard
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container image for honeypot
├── docker-compose.yml      # Multi-service orchestration
└── README.md              
```

## Logs & Evidence

- **Dwell Time**: Attack duration tracked by honeypot
- **Safety Violations**: Logs attempts to bypass discharge interlocks
- **Protocol Violations**: Unusual command sequences recorded
- **Register Access Patterns**: Which registers were queried/written

Check container logs with:
```bash
docker-compose logs -f water-tank-plc
```


### "No output" when running attack scripts
**Solution**: Ensure the honeypot server is running:
```bash
# Terminal 1: Start honeypot
python src/main.py

# Terminal 2: Run attack script
python src/test/attack_scanner.py
```

### Connection timeout errors
**Cause**: Firewall or port already in use  
**Solution**: 
```bash
netstat -an | grep 5020  # Check if port is available
# Change PORT in attack scripts if needed
```

### "ModbusTcpClient() takes 2 positional arguments" error
**Status**: Already fixed in this codebase (uses keyword arguments)  
**Details**: Uses modern pymodbus 3.6.4 API

## Use Cases

- 🔒 **Security Research**: Test ICS attack detection/response systems
- 📚 **Education**: Train operators on normal vs. anomalous behavior
- 🛡️ **Incident Response**: Simulate attacks without touching production systems

## References

- [Modbus/TCP Specification](http://www.modbus.org/)
- [Siemens S7 Protocol Documentation](https://support.industry.siemens.com/)
- [IEC 61850 Standard (Power Systems Communication)](https://en.wikipedia.org/wiki/IEC_61850)
- [Water Treatment Physics](https://www.awwa.org/)


## Author Notes

Built at GUC for industrial control system security research. The physics engine and safety constraints reflect real-world wastewater treatment facility behavior to maximize realism for security research.
