import asyncio
import detail2
import hardware
import json

clients = {}            # client_id writer
client_counter = 0
data_clients = {}       # client_id data writer
pending_connections = {}  # ip client_id
pending_connections2 = {}
total_power_consumption=0
total_carbon_emission=0


async def send_to(cid, message):
    writer = clients.get(cid)
    if writer:
        writer.write((message + "\n").encode())
        await writer.drain()


async def broadcast(sender_id, message):
    """Send message to all clients except sender."""
    for cid, writer in clients.items():
        if cid != sender_id:
            try:
                writer.write(f"[{sender_id}] {message}\n".encode())
                await writer.drain()
            except:
                pass


async def private_message(sender_id, target_id, message):
    writer = clients.get(target_id)
    if writer:
        writer.write(f"[Private from {sender_id}] {message}\n".encode())
        await writer.drain()
    else:
        await send_to(sender_id, f"Client {target_id} not found")



async def process_command(cid, cmd):

    if cmd == "/list":
        msg = "Connected clients:\n"
        for i in clients.keys():
            msg += f" - {i}\n"
        await send_to(cid, msg)
        return

    elif cmd == "/help":
        help_text = """
Available commands:
/list  - Show all connected clients.
/help  - Show this help message.
@<ID> <message>  - Send private message.
        """.strip()
        await send_to(cid, help_text)
        return

    else:
        await send_to(cid, "Invalid command")
        return




async def handle_client(reader, writer):
    global client_counter

    # Assign client ID
    client_counter += 1
    cid = client_counter
    clients[cid] = writer

    addr = writer.get_extra_info('peername')[0]
    pending_connections[addr] = cid 
    pending_connections2[addr] = cid # Match data connection to this ID

    writer.write(f"Connected! Your ID is {cid}. Type /help for commands.\n".encode())
    await writer.drain()

    print(f"Client {cid} connected from {addr}")
    await broadcast(0, f"Client {cid} joined the chat")

    try:
        while True:
            data = await reader.readline()
            if not data:
                break

            msg = data.decode().strip()

            # Private message: @ID message
            if msg.startswith("@"):
                try:
                    parts = msg.split(" ", 1)
                    target = int(parts[0][1:])
                    message = parts[1]
                    await private_message(cid, target, message)
                except:
                    await send_to(cid, "Invalid private message format")
                    continue

            # Commands: /list /help
            elif msg.startswith("/"):
                await process_command(cid, msg)
                continue

            else:
                print(f"[{cid}] {msg}")
                await broadcast(cid, msg)

    except Exception as e:
        print(f"Error with client {cid}: {e}")

    print(f"Client {cid} disconnected")
    clients.pop(cid, None)
    await broadcast(0, f"Client {cid} left")



async def server_input():
    loop = asyncio.get_event_loop()

    while True:
        text = await loop.run_in_executor(None, input, "Server: ")

        # Private message to a client
        if text.startswith("@"):
            try:
                parts = text.split(" ", 1)
                target_id = int(parts[0][1:])
                message = parts[1]

                writer = clients.get(target_id)
                if writer:
                    writer.write(f"[Private from Server]: {message}\n".encode())
                    await writer.drain()
                else:
                    print(f"Client {target_id} not found")

            except Exception:
                print("Invalid private message format. Use: @ID message")

        # Send command to client: #ID message
        elif text.startswith("#"):
            try:
                parts = text.split(" ", 1)
                target_id = int(parts[0][1:])
                message = parts[1]

                writer = clients.get(target_id)
                if writer:
                    writer.write(f"# {message}\n".encode())
                    await writer.drain()
                else:
                    print(f"Client {target_id} not found")

            except Exception:
                print("Invalid command message format. Use: #ID message")




        # Broadcast to all clients
        else:
            for writer in clients.values():
                writer.write(f"[Server]: {text}\n".encode())
                await writer.drain()



async def data_server(reader, writer):
    global total_power_consumption, total_carbon_emission
    addr = writer.get_extra_info('peername')[0]
    cid = pending_connections.pop(addr, None)

    if cid:
        data_clients[cid] = writer
        print(f"[DATA] Client {cid} connected (data channel)")
    else:
        print(f"[DATA] Unknown client from {addr}")

    try:
        while True:
            data = await reader.read(1048576)
            if not data:
                break

            print(f"[DATA] Received from {cid}")
            power,emission=detail2.deserialize_processes_fast(data)
            total_power_consumption=power+total_power_consumption
            total_carbon_emission=emission+total_carbon_emission
            print(f"Total Power Consumption so far : {total_power_consumption} Watt")
            print(f"Total Carbon Emission so far   : {total_carbon_emission:.4f} gram")


    except Exception as e:
        print("[DATA] Error:", e)






async def hard_info(reader, writer):
    addr = writer.get_extra_info('peername')[0]
    cid = pending_connections2.pop(addr, None)

    if cid:
        data_clients[cid] = writer
        print(f"[DATA] Client {cid} connected (data channel)")
    else:
        print(f"[DATA] Unknown client from {addr}")

    try:
        while True:
            data = await reader.read(1048576)
            if not data:
                break
            HI = data.decode().strip()
            hardware_list = json.loads(HI)

            print(f"[HARDWARE DATA] Received from {cid}")
            hardware.save_table_to_file(hardware_list)


    except Exception as e:
        pass



async def main():
    msg_server = await asyncio.start_server(handle_client, "127.0.0.1", 9000)
    data_srv = await asyncio.start_server(data_server, "127.0.0.1", 8000)
    hard_info = await asyncio.start_server(data_server, "127.0.0.1", 8888)

    asyncio.create_task(server_input())

    print("Servers running on ports 9000 (messages) and 8000 (data) and 8888 (Hardwareinfo)")

    await asyncio.gather(
        msg_server.serve_forever(),
        data_srv.serve_forever(),
        hard_info.serve_forever()

    )


asyncio.run(main())