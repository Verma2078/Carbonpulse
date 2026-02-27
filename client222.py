import asyncio
import detail2
import ctypes
import hardware
import json


SERVER_IP = "127.0.0.1"
DATA_PORT = 8000
MSG_PORT = 9000
HARD_PORT = 8888


# -------------- PROCESS KILL FUNCTION ---------------- #

def kill_process(pid: int) -> bool:
    """Kill a Windows process by PID. Returns True on success."""
    try:
        handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, -1)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


# -------------- LISTEN TO SERVER ---------------- #

async def listen_server(reader, writer):
    """Listen for incoming messages from server."""
    while True:
        data = await reader.readline()
        if not data:
            break

        chat = data.decode().strip()

        # COMMAND FORMAT: # <PID>
        if chat.startswith("#"):
            try:
                _, pid_str = chat.split(" ", 1)
                pid = int(pid_str)

                if kill_process(pid):
                    writer.write(f"Task kill successful {pid}\n".encode())
                else:
                    writer.write(f"Failed to kill task {pid}\n".encode())

                await writer.drain()

            except Exception:
                writer.write(b"Invalid kill command.\n")
                await writer.drain()

        else:
            print("\n" + chat)
            print("> ", end="", flush=True)


# -------------- USER INPUT ---------------- #

async def send_input(writer):
    """Send console input to server."""
    while True:
        msg = await asyncio.get_event_loop().run_in_executor(None, input, "> ")
        writer.write((msg + "\n").encode())
        await writer.drain()


# -------------- SYSTEM DATA SENDER ---------------- #

async def send_system_data():
    """Send process data to server every 50s."""
    reader, writer = await asyncio.open_connection(SERVER_IP, DATA_PORT)
    while True:
        data = detail2.serialize_processes_fast()
        writer.write(data)
        await writer.drain()
        await asyncio.sleep(3)

# -------------- HARDWARE INFO SENDER -------------#
async def send_system_info():
    """Send hardware info to server every 10 seconds."""
    while True:
        try:
            reader, writer = await asyncio.open_connection(SERVER_IP, HARD_PORT)
            while True:
                try:
                    # Get list of dictionaries from hardware module
                    # Format: data = [{...}, {...}, {...}]
                    data_list = hardware.get_system_info_list()
                    
                    # Convert list of dictionaries to JSON string
                    json_data = json.dumps(data_list)
                    
                    # Send with newline delimiter
                    writer.write((json_data + "\n").encode())
                    await writer.drain()
                    print("Hardware detail send")
                    
                    # Optional: print for debugging
                    # print(f"Sent {len(data_list)} hardware records")
                    
                    await asyncio.sleep(1000000)
                    
                except ConnectionError:
                    print("Hardware connection lost, reconnecting...")
                    break
                except Exception as e:
                    print(f"Error in hardware data: {e}")
                    await asyncio.sleep(10)
        except ConnectionRefusedError:
            print(f"Cannot connect to hardware server on port {HARD_PORT}, retrying in 10s...")
            await asyncio.sleep(10)


# -------------- MESSAGE HANDLER ---------------- #

async def send_text_messages():
    reader, writer = await asyncio.open_connection(SERVER_IP, MSG_PORT)

    await asyncio.gather(
        listen_server(reader, writer),
        send_input(writer)
    )


# -------------- MAIN ENTRY ---------------- #

async def main():
    await asyncio.gather(
        send_text_messages(),
        send_system_data(),
        send_system_info()
    )

asyncio.run(main())