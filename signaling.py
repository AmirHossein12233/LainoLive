import os
import json
import asyncio
import uuid

import websockets
from websockets.exceptions import ConnectionClosed


# ============================================================
# CONFIG
# ============================================================

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "10000"))


# ============================================================
# ROOMS
# ============================================================

rooms = {}

# websocket_info[websocket] = {
#     "room_id": "...",
#     "role": "host" / "viewer",
#     "viewer_id": "..."
# }

websocket_info = {}


# ============================================================
# SEND JSON
# ============================================================

async def send_json(websocket, data):
    try:
        await websocket.send(
            json.dumps(
                data,
                ensure_ascii=False
            )
        )
        return True

    except Exception as error:
        print(
            "Send error:",
            repr(error)
        )
        return False


# ============================================================
# ROOM INFO
# ============================================================

async def broadcast_room_info(room_id):
    if not room_id:
        return

    room = rooms.get(room_id)

    if not room:
        return

    viewers = room.get("viewers", {})
    viewer_count = len(viewers)

    message = {
        "type": "room-info",
        "room_id": room_id,
        "viewer_count": viewer_count
    }

    targets = []

    host = room.get("host")

    if host is not None:
        targets.append(host)

    targets.extend(
        viewers.values()
    )

    if not targets:
        return

    await asyncio.gather(
        *[
            send_json(
                websocket,
                message
            )
            for websocket in targets
        ],
        return_exceptions=True
    )


# ============================================================
# REMOVE VIEWER
# ============================================================

async def remove_viewer(websocket):
    info = websocket_info.get(websocket)

    if not info:
        return

    if info.get("role") != "viewer":
        return

    room_id = info.get("room_id")
    viewer_id = info.get("viewer_id")

    if not room_id or not viewer_id:
        return

    room = rooms.get(room_id)

    if not room:
        return

    viewers = room.setdefault(
        "viewers",
        {}
    )

    existed = viewer_id in viewers

    viewers.pop(
        viewer_id,
        None
    )

    host = room.get("host")

    if existed and host is not None:
        await send_json(
            host,
            {
                "type": "viewer-left",
                "viewer_id": viewer_id
            }
        )

    await broadcast_room_info(
        room_id
    )


# ============================================================
# REMOVE HOST
# ============================================================

async def remove_host(websocket):
    info = websocket_info.get(websocket)

    if not info:
        return

    if info.get("role") != "host":
        return

    room_id = info.get("room_id")

    if not room_id:
        return

    room = rooms.get(room_id)

    if not room:
        return

    if room.get("host") is not websocket:
        return

    viewers = list(
        room.get(
            "viewers",
            {}
        ).items()
    )

    for viewer_id, viewer_socket in viewers:
        await send_json(
            viewer_socket,
            {
                "type": "host-left",
                "room_id": room_id
            }
        )

        websocket_info.pop(
            viewer_socket,
            None
        )

    rooms.pop(
        room_id,
        None
    )


# ============================================================
# JOIN HOST
# ============================================================

async def join_host(websocket, message):
    room_id = str(
        message.get(
            "room_id",
            ""
        )
    ).strip()

    if not room_id:
        await send_json(
            websocket,
            {
                "type": "error",
                "message": "room_id is required"
            }
        )
        return

    current_info = websocket_info.get(
        websocket
    )

    if current_info:
        current_role = current_info.get(
            "role"
        )

        if current_role == "viewer":
            await remove_viewer(websocket)

        elif current_role == "host":
            await remove_host(websocket)

    room = rooms.get(room_id)

    if room is not None:
        existing_host = room.get(
            "host"
        )

        if (
            existing_host is not None
            and existing_host is not websocket
        ):
            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": "room already has a host"
                }
            )
            return

    room = rooms.setdefault(
        room_id,
        {
            "host": None,
            "viewers": {}
        }
    )

    room["host"] = websocket

    websocket_info[websocket] = {
        "room_id": room_id,
        "role": "host",
        "viewer_id": None
    }

    await send_json(
        websocket,
        {
            "type": "joined",
            "role": "host",
            "room_id": room_id,
            "viewer_count": len(
                room.get(
                    "viewers",
                    {}
                )
            )
        }
    )

    # اطلاع host از viewerهای موجود
    for viewer_id in list(
        room.get(
            "viewers",
            {}
        ).keys()
    ):
        await send_json(
            websocket,
            {
                "type": "viewer-joined",
                "viewer_id": viewer_id
            }
        )

    await broadcast_room_info(
        room_id
    )


# ============================================================
# JOIN VIEWER
# ============================================================

async def join_viewer(websocket, message):
    room_id = str(
        message.get(
            "room_id",
            ""
        )
    ).strip()

    if not room_id:
        await send_json(
            websocket,
            {
                "type": "error",
                "message": "room_id is required"
            }
        )
        return

    room = rooms.get(room_id)

    if room is None:
        await send_json(
            websocket,
            {
                "type": "error",
                "message": "room not found"
            }
        )
        return

    host = room.get("host")

    if host is None:
        await send_json(
            websocket,
            {
                "type": "error",
                "message": "host not found"
            }
        )
        return

    current_info = websocket_info.get(
        websocket
    )

    if current_info:
        current_role = current_info.get(
            "role"
        )

        if current_role == "viewer":
            await remove_viewer(websocket)

        elif current_role == "host":
            await remove_host(websocket)

            room = rooms.get(room_id)

            if room is None:
                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "room unavailable"
                    }
                )
                return

            host = room.get("host")

            if host is None:
                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "host unavailable"
                    }
                )
                return

    viewer_id = uuid.uuid4().hex[:16]

    room.setdefault(
        "viewers",
        {}
    )[viewer_id] = websocket

    websocket_info[websocket] = {
        "room_id": room_id,
        "role": "viewer",
        "viewer_id": viewer_id
    }

    await send_json(
        websocket,
        {
            "type": "joined",
            "role": "viewer",
            "room_id": room_id,
            "viewer_id": viewer_id,
            "viewer_count": len(
                room.get(
                    "viewers",
                    {}
                )
            )
        }
    )

    await send_json(
        host,
        {
            "type": "viewer-joined",
            "viewer_id": viewer_id
        }
    )

    await broadcast_room_info(
        room_id
    )


# ============================================================
# ROUTE WEBRTC SIGNALS
# ============================================================

async def route_signal(websocket, message):
    info = websocket_info.get(
        websocket
    )

    if not info:
        return

    room_id = info.get(
        "room_id"
    )

    role = info.get(
        "role"
    )

    if not room_id:
        return

    room = rooms.get(room_id)

    if not room:
        return

    message_type = message.get(
        "type"
    )

    # --------------------------------------------------------
    # HOST -> VIEWER
    # --------------------------------------------------------

    if (
        role == "host"
        and message_type in {
            "offer",
            "ice-candidate"
        }
    ):
        viewer_id = str(
            message.get(
                "viewer_id",
                ""
            )
        )

        if not viewer_id:
            return

        target = room.get(
            "viewers",
            {}
        ).get(
            viewer_id
        )

        if target is None:
            return

        await send_json(
            target,
            message
        )

        return

    # --------------------------------------------------------
    # VIEWER -> HOST
    # --------------------------------------------------------

    if (
        role == "viewer"
        and message_type in {
            "answer",
            "ice-candidate"
        }
    ):
        host = room.get(
            "host"
        )

        if host is None:
            return

        viewer_id = info.get(
            "viewer_id"
        )

        forwarded = dict(
            message
        )

        forwarded["viewer_id"] = viewer_id

        await send_json(
            host,
            forwarded
        )


# ============================================================
# CHAT
# ============================================================

async def route_chat(websocket, message):
    info = websocket_info.get(
        websocket
    )

    if not info:
        return

    room_id = info.get(
        "room_id"
    )

    if not room_id:
        return

    room = rooms.get(room_id)

    if not room:
        return

    username = str(
        message.get(
            "username",
            "کاربر"
        )
    ).strip()

    text = str(
        message.get(
            "message",
            ""
        )
    ).strip()

    if not text:
        return

    if len(text) > 500:
        text = text[:500]

    chat_message = {
        "type": "chat-message",
        "room_id": room_id,
        "username": username or "کاربر",
        "message": text
    }

    targets = []

    host = room.get("host")

    if host is not None:
        targets.append(host)

    targets.extend(
        room.get(
            "viewers",
            {}
        ).values()
    )

    await asyncio.gather(
        *[
            send_json(
                target,
                chat_message
            )
            for target in targets
        ],
        return_exceptions=True
    )


# ============================================================
# PING
# ============================================================

async def handle_ping(websocket):
    await send_json(
        websocket,
        {
            "type": "pong"
        }
    )


# ============================================================
# DISCONNECT
# ============================================================

async def disconnect_client(websocket):
    info = websocket_info.get(
        websocket
    )

    if not info:
        return

    role = info.get(
        "role"
    )

    try:
        if role == "viewer":
            await remove_viewer(websocket)

        elif role == "host":
            await remove_host(websocket)

    finally:
        websocket_info.pop(
            websocket,
            None
        )


# ============================================================
# MESSAGE HANDLER
# ============================================================

async def handle_message(websocket, message):
    if not isinstance(
        message,
        dict
    ):
        return

    message_type = message.get(
        "type"
    )

    if message_type == "join":
        role = str(
            message.get(
                "role",
                ""
            )
        ).lower().strip()

        if role == "host":
            await join_host(
                websocket,
                message
            )

        elif role == "viewer":
            await join_viewer(
                websocket,
                message
            )

        else:
            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": "invalid role"
                }
            )

        return

    if message_type in {
        "offer",
        "answer",
        "ice-candidate"
    }:
        await route_signal(
            websocket,
            message
        )
        return

    if message_type == "chat-message":
        await route_chat(
            websocket,
            message
        )
        return

    if message_type == "room-info":
        info = websocket_info.get(
            websocket
        )

        if info:
            await broadcast_room_info(
                info.get(
                    "room_id"
                )
            )

        return

    if message_type == "ping":
        await handle_ping(
            websocket
        )
        return

    if message_type == "ready":
        info = websocket_info.get(
            websocket
        )

        if info and info.get(
            "role"
        ) == "viewer":
            room_id = info.get(
                "room_id"
            )

            viewer_id = info.get(
                "viewer_id"
            )

            room = rooms.get(
                room_id
            )

            if room:
                host = room.get(
                    "host"
                )

                if host:
                    await send_json(
                        host,
                        {
                            "type": "viewer-ready",
                            "viewer_id": viewer_id
                        }
                    )

        return

    if message_type == "leave":
        await disconnect_client(
            websocket
        )
        return

    # برای سازگاری با نسخه‌های قبلی
    if message_type == "negotiationneeded":
        return

    await send_json(
        websocket,
        {
            "type": "unknown",
            "message": "unknown message type"
        }
    )


# ============================================================
# WEBSOCKET HANDLER
# ============================================================

async def handler(websocket):
    websocket_info[websocket] = {
        "room_id": None,
        "role": None,
        "viewer_id": None
    }

    try:
        async for raw_message in websocket:

            try:
                message = json.loads(
                    raw_message
                )

            except (
                json.JSONDecodeError,
                TypeError
            ):
                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "invalid JSON"
                    }
                )
                continue

            try:
                await handle_message(
                    websocket,
                    message
                )

            except Exception as error:
                print(
                    "Message handling error:",
                    repr(error)
                )

                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "server error"
                    }
                )

    except ConnectionClosed:
        pass

    except Exception as error:
        print(
            "WebSocket error:",
            repr(error)
        )

    finally:
        try:
            await disconnect_client(
                websocket
            )

        except Exception as error:
            print(
                "Disconnect error:",
                repr(error)
            )


# ============================================================
# MAIN
# ============================================================

async def main():
    print(
        "============================================="
    )

    print(
        "LainoLive Signaling Server"
    )

    print(
        "============================================="
    )

    print(
        f"Listening on {HOST}:{PORT}"
    )

    async with websockets.serve(
        handler,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        max_size=1024 * 1024
    ):
        await asyncio.Future()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(
            main()
        )

    except KeyboardInterrupt:
        print(
            "\nLainoLive Signaling Server stopped."
        )
