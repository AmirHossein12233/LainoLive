import asyncio
import json
import os
from collections import defaultdict
from typing import Dict, Set

import websockets
from websockets.server import ServerConnection


# =========================================================
# تنظیمات
# =========================================================

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "10000"))

# حداکثر اندازه پیام WebSocket
MAX_MESSAGE_SIZE = 1024 * 1024

# =========================================================
# اتاق‌ها
# =========================================================

# room_id -> set of connected websocket clients
rooms: Dict[str, Set[ServerConnection]] = defaultdict(set)

# websocket -> اطلاعات اتصال
connections: Dict[ServerConnection, dict] = {}

rooms_lock = asyncio.Lock()


# =========================================================
# JSON
# =========================================================

def safe_json_loads(raw):
    try:
        data = json.loads(raw)

        if isinstance(data, dict):
            return data

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError
    ):
        pass

    return None


def json_message(data):
    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    )


# =========================================================
# ارسال پیام
# =========================================================

async def send_json(
    websocket,
    data
):
    try:
        await websocket.send(
            json_message(data)
        )
        return True

    except Exception:
        return False


async def send_to_room(
    room_id,
    data,
    exclude=None
):
    async with rooms_lock:

        clients = list(
            rooms.get(
                room_id,
                set()
            )
        )

    if not clients:
        return

    message = json_message(data)

    dead_clients = []

    for client in clients:

        if client is exclude:
            continue

        try:

            await client.send(
                message
            )

        except Exception:

            dead_clients.append(
                client
            )

    if dead_clients:

        await remove_dead_clients(
            room_id,
            dead_clients
        )


async def remove_dead_clients(
    room_id,
    clients
):

    async with rooms_lock:

        room = rooms.get(
            room_id
        )

        if not room:
            return

        for client in clients:

            room.discard(
                client
            )

            connections.pop(
                client,
                None
            )

        if not room:

            rooms.pop(
                room_id,
                None
            )


# =========================================================
# پیدا کردن کلاینت‌های اتاق
# =========================================================

async def get_room_clients(
    room_id
):
    async with rooms_lock:

        return list(
            rooms.get(
                room_id,
                set()
            )
        )


# =========================================================
# تعیین نقش
# =========================================================

def normalize_role(role):

    role = str(
        role or ""
    ).strip().lower()

    if role in {
        "host",
        "broadcaster",
        "publisher",
        "streamer",
        "live"
    }:

        return "host"

    if role in {
        "viewer",
        "watcher",
        "audience"
    }:

        return "viewer"

    return role


# =========================================================
# JOIN ROOM
# =========================================================

async def join_room(
    websocket,
    room_id,
    role
):

    if not room_id:

        await send_json(
            websocket,
            {
                "type": "error",
                "message": "room_id is required"
            }
        )

        return False

    role = normalize_role(
        role
    )

    if role not in {
        "host",
        "viewer"
    }:

        await send_json(
            websocket,
            {
                "type": "error",
                "message": "invalid role"
            }
        )

        return False

    old_room = connections.get(
        websocket,
        {}
    ).get(
        "room_id"
    )

    if old_room:

        await leave_room(
            websocket,
            notify=True
        )

    async with rooms_lock:

        room = rooms[
            room_id
        ]

        existing_clients = list(
            room
        )

        room.add(
            websocket
        )

        connections[
            websocket
        ] = {
            "room_id":
                room_id,

            "role":
                role
        }

    # اطلاعات اتاق برای تازه‌وارد
    await send_json(
        websocket,
        {
            "type":
                "joined",

            "room_id":
                room_id,

            "role":
                role,

            "members":
                len(existing_clients) + 1
        }
    )

    # اگر viewer وارد شد، host را خبر کن
    if role == "viewer":

        host_clients = []

        for client in existing_clients:

            info = connections.get(
                client,
                {}
            )

            if info.get(
                "role"
            ) == "host":

                host_clients.append(
                    client
                )

        for host in host_clients:

            await send_json(
                host,
                {
                    "type":
                        "viewer-joined",

                    "room_id":
                        room_id
                }
            )

        # اگر host از قبل داخل اتاق بود
        # به viewer هم اطلاع بده
        if host_clients:

            await send_json(
                websocket,
                {
                    "type":
                        "host-present",

                    "room_id":
                        room_id
                }
            )

    # اگر host بعد از viewer وارد شد
    elif role == "host":

        viewer_clients = []

        for client in existing_clients:

            info = connections.get(
                client,
                {}
            )

            if info.get(
                "role"
            ) == "viewer":

                viewer_clients.append(
                    client
                )

        for viewer in viewer_clients:

            await send_json(
                viewer,
                {
                    "type":
                        "host-present",

                    "room_id":
                        room_id
                }
            )

    return True


# =========================================================
# LEAVE ROOM
# =========================================================

async def leave_room(
    websocket,
    notify=True
):

    info = connections.get(
        websocket,
        {}
    )

    room_id = info.get(
        "room_id"
    )

    role = info.get(
        "role"
    )

    if not room_id:

        connections.pop(
            websocket,
            None
        )

        return

    async with rooms_lock:

        room = rooms.get(
            room_id
        )

        if room:

            room.discard(
                websocket
            )

            if not room:

                rooms.pop(
                    room_id,
                    None
                )

        connections.pop(
            websocket,
            None
        )

    if not notify:
        return

    if role == "viewer":

        await send_to_room(
            room_id,
            {
                "type":
                    "viewer-left",

                "room_id":
                    room_id
            }
        )

    elif role == "host":

        await send_to_room(
            room_id,
            {
                "type":
                    "host-left",

                "room_id":
                    room_id
            }
        )


# =========================================================
# RELAY پیام WebRTC
# =========================================================

async def relay_message(
    websocket,
    data
):

    info = connections.get(
        websocket,
        {}
    )

    room_id = info.get(
        "room_id"
    )

    if not room_id:

        await send_json(
            websocket,
            {
                "type":
                    "error",

                "message":
                    "join a room first"
            }
        )

        return

    message_type = str(
        data.get(
            "type",
            ""
        )
    ).strip().lower()

    # پیام‌های معتبر برای WebRTC
    allowed_types = {
        "offer",
        "answer",
        "ice-candidate",
        "candidate",
        "ice",
        "negotiationneeded"
    }

    if message_type not in allowed_types:

        return

    # مشخصات فرستنده
    data["room_id"] = room_id

    # بعضی کلاینت‌ها از sender استفاده می‌کنند
    if "sender_role" not in data:

        data["sender_role"] = (
            info.get(
                "role"
            )
        )

    # relay به همه اعضای دیگر
    await send_to_room(
        room_id,
        data,
        exclude=websocket
    )


# =========================================================
# پیام‌های کمکی
# =========================================================

async def handle_ping(
    websocket
):

    await send_json(
        websocket,
        {
            "type":
                "pong"
        }
    )


async def send_room_info(
    websocket
):

    info = connections.get(
        websocket,
        {}
    )

    room_id = info.get(
        "room_id"
    )

    if not room_id:

        await send_json(
            websocket,
            {
                "type":
                    "room-info",

                "room_id":
                    None,

                "members":
                    0
            }
        )

        return

    clients = await get_room_clients(
        room_id
    )

    roles = []

    for client in clients:

        client_info = connections.get(
            client,
            {}
        )

        roles.append(
            client_info.get(
                "role"
            )
        )

    await send_json(
        websocket,
        {
            "type":
                "room-info",

            "room_id":
                room_id,

            "members":
                len(clients),

            "hosts":
                roles.count(
                    "host"
                ),

            "viewers":
                roles.count(
                    "viewer"
                )
        }
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def handle_message(
    websocket,
    data
):

    message_type = str(
        data.get(
            "type",
            ""
        )
    ).strip().lower()

    # JOIN
    if message_type in {
        "join",
        "room-join"
    }:

        room_id = str(
            data.get(
                "room_id",
                data.get(
                    "stream_id",
                    ""
                )
            )
        ).strip()

        role = normalize_role(
            data.get(
                "role",
                data.get(
                    "mode",
                    ""
                )
            )
        )

        await join_room(
            websocket,
            room_id,
            role
        )

        return

    # LEAVE
    if message_type in {
        "leave",
        "room-leave"
    }:

        await leave_room(
            websocket,
            notify=True
        )

        return

    # PING
    if message_type in {
        "ping",
        "heartbeat"
    }:

        await handle_ping(
            websocket
        )

        return

    # ROOM INFO
    if message_type in {
        "room-info",
        "get-room-info"
    }:

        await send_room_info(
            websocket
        )

        return

    # WebRTC
    if message_type in {
        "offer",
        "answer",
        "ice-candidate",
        "candidate",
        "ice",
        "negotiationneeded"
    }:

        await relay_message(
            websocket,
            data
        )

        return

    # Unknown
    await send_json(
        websocket,
        {
            "type":
                "error",

            "message":
                "unknown message type",

            "received":
                message_type
        }
    )


# =========================================================
# CLIENT HANDLER
# =========================================================

async def client_handler(
    websocket: ServerConnection
):

    remote = None

    try:

        remote = websocket.remote_address

        print(
            f"[CONNECT] {remote}"
        )

        await send_json(
            websocket,
            {
                "type":
                    "connected",

                "service":
                    "LainoLive Signaling",

                "version":
                    "1.0"
            }
        )

        async for raw_message in websocket:

            # جلوگیری از پیام بسیار بزرگ
            if (
                isinstance(
                    raw_message,
                    str
                )
                and len(raw_message.encode(
                    "utf-8"
                )) > MAX_MESSAGE_SIZE
            ):

                await send_json(
                    websocket,
                    {
                        "type":
                            "error",

                        "message":
                            "message too large"
                    }
                )

                continue

            data = safe_json_loads(
                raw_message
            )

            if data is None:

                await send_json(
                    websocket,
                    {
                        "type":
                            "error",

                        "message":
                            "invalid json"
                    }
                )

                continue

            await handle_message(
                websocket,
                data
            )

    except websockets.exceptions.ConnectionClosed:

        pass

    except Exception as error:

        print(
            f"[CLIENT ERROR] {remote}: {error}"
        )

    finally:

        await leave_room(
            websocket,
            notify=True
        )

        print(
            f"[DISCONNECT] {remote}"
        )


# =========================================================
# CLEAN EMPTY ROOMS
# =========================================================

async def cleanup_rooms():

    while True:

        try:

            await asyncio.sleep(
                60
            )

            async with rooms_lock:

                empty_rooms = [
                    room_id
                    for room_id, clients
                    in rooms.items()
                    if not clients
                ]

                for room_id in empty_rooms:

                    rooms.pop(
                        room_id,
                        None
                    )

            if empty_rooms:

                print(
                    "[CLEANUP] Removed rooms:",
                    empty_rooms
                )

        except asyncio.CancelledError:

            break

        except Exception as error:

            print(
                "[CLEANUP ERROR]",
                error
            )


# =========================================================
# STATUS LOG
# =========================================================

async def status_logger():

    while True:

        try:

            await asyncio.sleep(
                30
            )

            async with rooms_lock:

                room_count = len(
                    rooms
                )

                client_count = sum(
                    len(clients)
                    for clients
                    in rooms.values()
                )

            print(
                f"[STATUS] rooms={room_count} "
                f"clients={client_count}"
            )

        except asyncio.CancelledError:

            break

        except Exception as error:

            print(
                "[STATUS ERROR]",
                error
            )


# =========================================================
# MAIN
# =========================================================

async def main():

    print("=" * 60)

    print("LainoLive Signaling Server")

    print("=" * 60)

    print(
        f"Listening on: "
        f"0.0.0.0:{PORT}"
    )

    print(
        f"WebSocket URL: "
        f"ws://127.0.0.1:{PORT}"
    )

    print(
        "WebRTC signaling: ENABLED"
    )

    print(
        "Multi-room: ENABLED"
    )

    print("=" * 60)

    cleanup_task = asyncio.create_task(
        cleanup_rooms()
    )

    status_task = asyncio.create_task(
        status_logger()
    )

    try:

        async with websockets.serve(
            client_handler,
            HOST,
            PORT,
            max_size=MAX_MESSAGE_SIZE,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=10
        ):

            print(
                "Signaling server started."
            )

            await asyncio.Future()

    except KeyboardInterrupt:

        print(
            "\nSignaling server stopped."
        )

    finally:

        cleanup_task.cancel()
        status_task.cancel()

        await asyncio.gather(
            cleanup_task,
            status_task,
            return_exceptions=True
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "\nStopped."
        )
