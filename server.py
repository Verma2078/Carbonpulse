"""
Monitoring System Server — Silent
===================================
Runs fully in background. No terminal input/output.
All interaction happens through the dashboard (WebSocket port 9999).

Ports:
  9000 — TCP chat
  8000 — TCP binary process/metrics
  8888 — TCP hardware JSON
  9999 — WebSocket (dashboard)

Requirements:
  pip install websockets
"""

import asyncio
import json
import time
import websockets
import detail2
import hardware

# ── State ─────────────────────────────────────────────────────────────
clients = {}
client_info = {}
client_counter = 0

pending_connections  = {}
pending_connections2 = {}

total_power_consumption = 0.0
total_carbon_emission   = 0.0

client_metrics  = {}
client_hardware = {}

ws_clients: set = set()


# ── WebSocket helpers ─────────────────────────────────────────────────

async def ws_broadcast(payload: dict):
    global ws_clients
    if not ws_clients:
        return
    msg  = json.dumps(payload)
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    ws_clients -= dead


async def ws_handler(websocket):
    ws_clients.add(websocket)
    await websocket.send(json.dumps(build_full_state()))
    try:
        async for raw in websocket:
            try:
                await handle_ws_command(json.loads(raw))
            except Exception:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)


async def handle_ws_command(data: dict):
    t = data.get("type")

    if t == "chat":
        text = data.get("text", "").strip()
        if not text:
            return
        for writer in clients.values():
            try:
                writer.write(f"[Server]: {text}\n".encode())
                await writer.drain()
            except Exception:
                pass
        await ws_broadcast({"type": "chat", "from": "Server",
                             "text": text, "ts": _ts(), "color": "#FFD93D"})

    elif t == "private":
        cid    = data.get("cid")
        text   = data.get("text", "").strip()
        writer = clients.get(cid)
        if writer and text:
            try:
                writer.write(f"[Private from Server]: {text}\n".encode())
                await writer.drain()
            except Exception:
                pass
            await ws_broadcast({"type": "chat", "from": "Server", "to": str(cid),
                                 "text": text, "private": True,
                                 "ts": _ts(), "color": "#CC5DE8"})

    elif t == "kill":
        cid    = data.get("cid")
        pid    = data.get("pid")
        writer = clients.get(cid)
        if writer and pid:
            try:
                writer.write(f"# {pid}\n".encode())
                await writer.drain()
            except Exception:
                pass
            await ws_broadcast({"type": "system",
                                 "text": f"Kill signal → PID {pid} on Client #{cid}",
                                 "ts": _ts()})

    elif t == "list":
        await ws_broadcast(build_full_state())

    elif t == "client_chat":
        # Public broadcast from a client dashboard (via WebSocket)
        from_cid = data.get("from_cid")
        text     = data.get("text", "").strip()
        if not from_cid or not text:
            return
        # Relay to all TCP clients
        for writer in clients.values():
            try:
                writer.write(f"[#{from_cid}]: {text}\n".encode())
                await writer.drain()
            except Exception:
                pass
        await ws_broadcast({"type": "chat", "from": str(from_cid),
                             "text": text, "ts": _ts(), "color": "#4D9EFF"})

    elif t == "client_private":
        # Private message from a client dashboard to server or another client
        from_cid = data.get("from_cid")
        to       = data.get("to")        # "server" or an integer cid
        text     = data.get("text", "").strip()
        if not from_cid or not text:
            return

        if to == "server":
            # Deliver only to server dashboard (ws_broadcast with flag)
            await ws_broadcast({"type": "chat", "from": str(from_cid),
                                 "to": "Server", "text": text, "private": True,
                                 "ts": _ts(), "color": "#CC5DE8"})
        else:
            # Private to another TCP client
            target_cid = int(to)
            writer     = clients.get(target_cid)
            if writer:
                try:
                    writer.write(f"[Private from #{from_cid}]: {text}\n".encode())
                    await writer.drain()
                except Exception:
                    pass
            # Also broadcast so both dashboards see it
            await ws_broadcast({"type": "chat", "from": str(from_cid),
                                 "to": str(target_cid), "text": text, "private": True,
                                 "ts": _ts(), "color": "#CC5DE8"})


def build_full_state() -> dict:
    return {
        "type": "full_state",
        "clients": [
            {
                "cid": cid,
                "addr": client_info.get(cid, {}).get("addr", "?"),
                "connected_at": client_info.get(cid, {}).get("connected_at", 0),
                "metrics":  client_metrics.get(cid, {}),
                "hardware": client_hardware.get(cid, []),
            }
            for cid in clients
        ],
        "total_power":    round(total_power_consumption, 2),
        "total_emission": round(total_carbon_emission, 4),
        "ts": _ts(),
    }


def _ts():
    return time.strftime("%H:%M:%S")


# ── TCP Chat — port 9000 ──────────────────────────────────────────────

async def handle_client(reader, writer):
    global client_counter

    client_counter += 1
    cid  = client_counter
    addr = writer.get_extra_info("peername")[0]

    clients[cid]     = writer
    client_info[cid] = {"addr": addr, "connected_at": time.time()}
    pending_connections[addr]  = cid
    pending_connections2[addr] = cid

    try:
        writer.write(f"CONNECTED:{cid}\n".encode())
        await writer.drain()
    except Exception:
        pass

    await ws_broadcast({"type": "system",
                         "text": f"Client #{cid} connected from {addr}", "ts": _ts()})
    await ws_broadcast(build_full_state())

    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            msg = data.decode().strip()
            if not msg:
                continue

            if msg.startswith("@"):
                try:
                    parts   = msg.split(" ", 1)
                    target  = int(parts[0][1:])
                    message = parts[1]
                    w2      = clients.get(target)
                    if w2:
                        w2.write(f"[Private from #{cid}]: {message}\n".encode())
                        await w2.drain()
                    await ws_broadcast({"type": "chat", "from": str(cid),
                                         "to": str(target), "text": message,
                                         "private": True, "ts": _ts(), "color": "#CC5DE8"})
                except Exception:
                    pass

            elif msg.startswith("Task kill") or msg.startswith("Failed to kill"):
                await ws_broadcast({"type": "system",
                                     "text": f"Client #{cid}: {msg}", "ts": _ts()})
            else:
                for c2, w2 in clients.items():
                    if c2 != cid:
                        try:
                            w2.write(f"[#{cid}]: {msg}\n".encode())
                            await w2.drain()
                        except Exception:
                            pass
                await ws_broadcast({"type": "chat", "from": str(cid),
                                     "text": msg, "ts": _ts(), "color": "#4D9EFF"})

    except Exception:
        pass

    clients.pop(cid, None)
    client_info.pop(cid, None)
    client_metrics.pop(cid, None)

    await ws_broadcast({"type": "system",
                         "text": f"Client #{cid} disconnected", "ts": _ts()})
    await ws_broadcast(build_full_state())


# ── Metrics — port 8000 ───────────────────────────────────────────────

async def data_server(reader, writer):
    global total_power_consumption, total_carbon_emission

    addr = writer.get_extra_info("peername")[0]
    cid  = None
    for _ in range(10):
        cid = pending_connections.pop(addr, None)
        if cid is not None:
            break
        await asyncio.sleep(0.5)

    try:
        while True:
            data = await reader.read(1048576)
            if not data:
                break

            power, emission = detail2.deserialize_processes_fast(data)
            total_power_consumption += power
            total_carbon_emission   += emission

            snapshot = _parse_snapshot(data, power, emission)
            if cid:
                client_metrics[cid] = snapshot

            await ws_broadcast({
                "type": "metrics_update",
                "cid":  cid,
                "snapshot": snapshot,
                "total_power":    round(total_power_consumption, 2),
                "total_emission": round(total_carbon_emission, 4),
                "ts": _ts(),
            })
    except Exception:
        pass


def _parse_snapshot(data: bytes, power, emission) -> dict:
    try:
        ts    = int.from_bytes(data[0:8], "little")
        count = int.from_bytes(data[8:12], "little")
        cpu   = data[12]
        ram   = data[13]
        gpu   = data[14]
        pos   = 19
        procs = []
        for _ in range(count):
            pid      = int.from_bytes(data[pos:pos+4], "little"); pos += 4
            nlen     = int.from_bytes(data[pos:pos+2], "little"); pos += 2
            name     = data[pos:pos+nlen].decode("utf-8");        pos += nlen
            procs.append({"pid": pid, "name": name})
        return {"ts": time.ctime(ts), "cpu": cpu, "ram": ram, "gpu": gpu,
                "power": power, "emission": round(emission, 4), "processes": procs}
    except Exception:
        return {"power": power, "emission": round(emission, 4)}


# ── Hardware — port 8888 ──────────────────────────────────────────────

async def hard_info_server(reader, writer):
    addr = writer.get_extra_info("peername")[0]

    # Retry CID lookup — hardware connection may arrive before chat registers the CID
    cid = None
    for _ in range(10):
        cid = pending_connections2.pop(addr, None)
        if cid is not None:
            break
        await asyncio.sleep(0.5)

    try:
        while True:
            data = await reader.read(1048576)
            if not data:
                break

            raw = data.decode().strip()
            try:
                hw_list = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                try:
                    import ast
                    hw_list = ast.literal_eval(raw)
                except Exception:
                    continue  # skip unparseable packet

            if cid is not None:
                client_hardware[cid] = hw_list
            await ws_broadcast({"type": "hardware_update", "cid": cid,
                                 "hardware": hw_list, "ts": _ts()})
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────

async def main():
    msg_srv  = await asyncio.start_server(handle_client,    "0.0.0.0", 9000)
    data_srv = await asyncio.start_server(data_server,      "0.0.0.0", 8000)
    hw_srv   = await asyncio.start_server(hard_info_server, "0.0.0.0", 8888)
    ws_srv   = await websockets.serve(ws_handler,           "0.0.0.0", 9999)

    await asyncio.gather(
        msg_srv.serve_forever(),
        data_srv.serve_forever(),
        hw_srv.serve_forever(),
        ws_srv.wait_closed(),
    )


asyncio.run(main())
