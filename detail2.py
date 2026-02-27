import psutil
import win32gui
import win32process
import time
import GPUtil
total_power_consumption=None
total_carbon_emission=None



def get_gpu_usage():
    try:
        g = GPUtil.getGPUs()
        return int(g[0].load * 100) if g else 0
    except:
        return 0


def get_visible_pids():
    pids = set()
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                pids.add(pid)
    win32gui.EnumWindows(cb, None)
    return pids


def serialize_processes_fast():
    """Ultra-fast serialization - returns binary data"""
    visible_pids = get_visible_pids()
    
    max_size = len(visible_pids) * 50 + 50
    data = bytearray(max_size)

    timestamp = int(time.time())
    cpu = int(psutil.cpu_percent(interval=0))
    ram = int(psutil.virtual_memory().percent)
    gpu = get_gpu_usage()

    power = int((50*cpu/100) + (10*ram/100) + (95*gpu/100))
    emission = (power * 0.70) / 3600        # float small number
    emission_int = int(emission * 1000)     # store with 3 decimals

    # ---- HEADER ----
    data[0:8] = timestamp.to_bytes(8, "little")
    data[8:12] = (0).to_bytes(4, "little")              # placeholder count
    data[12] = cpu                                      # 1 byte
    data[13] = ram                                      # 1 byte
    data[14] = gpu                                      # 1 byte
    data[15:17] = power.to_bytes(2, "little")           # 2 bytes now FIXED
    data[17:19] = emission_int.to_bytes(2, "little")    # 2 bytes FIXED

    pos = 19
    count = 0

    # ---- PROCESS LIST ----
    for p in psutil.process_iter(["pid", "name"]):
        if p.pid not in visible_pids:
            continue

        try:
            pid = p.pid
            name = p.info["name"][:100]
            name_bytes = name.encode("utf-8")
            name_len = len(name_bytes)

            # PID
            data[pos:pos+4] = pid.to_bytes(4, "little")
            pos += 4

            # Name length
            data[pos:pos+2] = name_len.to_bytes(2, "little")
            pos += 2

            # Name bytes
            data[pos:pos+name_len] = name_bytes
            pos += name_len

            count += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Write process count
    data[8:12] = count.to_bytes(4, "little")

    return bytes(data[:pos])




def deserialize_processes_fast(data: bytes):
    """Ultra-fast decoder for custom binary format"""

    timestamp = int.from_bytes(data[0:8], "little")
    count = int.from_bytes(data[8:12], "little")
    cpu = data[12]
    ram = data[13]
    gpu = data[14]

    power = int.from_bytes(data[15:17], "little")           # FIXED
    emission = int.from_bytes(data[17:19], "little") / 1000 # FIXED

    print("\n=== SYSTEM USAGE ===")
    print(f"Timestamp        : {timestamp} ({time.ctime(timestamp)})")
    print(f"CPU Usage        : {cpu}%")
    print(f"RAM Usage        : {ram}%")
    print(f"GPU Usage        : {gpu}%")
    print(f"Power Consumption: {power} W (approx)")
    print(f"CO₂ Emission     : {emission} g/sec (approx)")

    print("\n=== PROCESSES ===")
    print(f"Total Visible Processes: {count}")
    print("-" * 50)
    print("PID      | Name")
    print("-" * 50)

    pos = 19
    processes = []

    for _ in range(count):
        pid = int.from_bytes(data[pos:pos+4], "little")
        pos += 4

        name_len = int.from_bytes(data[pos:pos+2], "little")
        pos += 2

        name = data[pos:pos+name_len].decode("utf-8")
        pos += name_len

        processes.append((pid, name))
        print(f"{pid:<8} | {name}")

    print("-" * 50)
    print(f"Successfully decoded {len(processes)} processes")
    return (power,emission)