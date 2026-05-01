"""
Monitoring System Client — Silent
====================================
Runs fully in the background. No terminal input/output.
Sends metrics, hardware info, and receives commands silently.

The client has NO chat UI — all chat/commands come from the
server dashboard and are handled here automatically.

Requirements:
  pip install psutil GPUtil pywin32 py-cpuinfo pyopencl pandas
"""

import asyncio
import ctypes
import json
import sys
import detail2
import hardware

SERVER_IP     = "127.0.0.1"   # ← change to server IP if remote
MSG_PORT      = 9000
DATA_PORT     = 8000
HARD_PORT     = 8888
RECONNECT_SEC = 5


# ── Process kill (Windows) ────────────────────────────────────────────

def kill_process(pid: int) -> bool:
    try:
        handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, -1)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


# ── Chat channel — port 9000 ──────────────────────────────────────────
# Client only listens for incoming server commands (kill, private msg).
# It does NOT print anything or take user input.

async def run_chat():
    while True:
        try:
            reader, writer = await asyncio.open_connection(SERVER_IP, MSG_PORT)

            async for data in reader:
                line = data.decode().strip()
                if not line:
                    continue

                # Kill command: # <PID>
                if line.startswith("#"):
                    try:
                        _, pid_str = line.split(" ", 1)
                        pid = int(pid_str.strip())
                        if kill_process(pid):
                            writer.write(f"Task kill successful {pid}\n".encode())
                        else:
                            writer.write(f"Failed to kill task {pid}\n".encode())
                        await writer.drain()
                    except Exception:
                        pass

                # Server confirmation of connection — ignore
                # Private messages — silently acknowledged (no terminal)

        except ConnectionRefusedError:
            pass
        except Exception:
            pass

        await asyncio.sleep(RECONNECT_SEC)


# ── Metrics channel — port 8000 ───────────────────────────────────────

async def run_metrics():
    while True:
        try:
            reader, writer = await asyncio.open_connection(SERVER_IP, DATA_PORT)
            while True:
                data = detail2.serialize_processes_fast()
                writer.write(data)
                await writer.drain()
                await asyncio.sleep(3)

        except ConnectionRefusedError:
            pass
        except Exception:
            pass

        await asyncio.sleep(RECONNECT_SEC)


# ── Hardware channel — port 8888 ──────────────────────────────────────

async def run_hardware():
    while True:
        try:
            reader, writer = await asyncio.open_connection(SERVER_IP, HARD_PORT)

            # Send once on connect
            payload = json.dumps(hardware.get_system_info_list()) + "\n"
            writer.write(payload.encode())
            await writer.drain()
            

            # Re-send every 10 minutes
            while True:
                await asyncio.sleep(600)
                payload = json.dumps(hardware.get_system_info_list()) + "\n"
                writer.write(payload.encode())
                await writer.drain()

        except ConnectionRefusedError:
            pass
        except Exception:
            pass

        await asyncio.sleep(RECONNECT_SEC)


# ── Main ──────────────────────────────────────────────────────────────

async def main():
    await asyncio.gather(
        run_chat(),
        run_metrics(),
        run_hardware(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
