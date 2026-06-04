import snap7
from snap7.util import get_real

client = snap7.client.Client()
try:
    client.connect('127.0.0.1', 0, 1) # Localhost, Rack 0, Slot 1
    # Read 16 bytes from DB1 starting at offset 0
    data = client.db_read(1, 0, 16)
    level = get_real(data, 4)
    pressure = get_real(data, 8)
    temp = get_real(data, 12)
    print(f"S7 Read -> Level: {level:.1f}%, Pressure: {pressure:.3f}, Temp: {temp:.1f}")
    client.disconnect()
except Exception as e:
    print(f"Connection Failed: {e}")