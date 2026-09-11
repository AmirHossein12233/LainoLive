import asyncio
import json
import os
import uuid
from collections import defaultdict

import websockets


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "10000"))


# =========================================================
# ROOMS
# =========================================================

rooms = defaultdict(
    lambda: {
        "host": None,
        "viewers": {}
    }
)


# websocket_info[websocket] = {
#     "room_id": "...",
#     "role": "host" or "viewer",
#     "viewer_id": "..."
# }

websocket_info = {}


# =========================================================
# SEND JSON
# =========================================================

async def send_json(websocket, payload):
    if websocket is None:
        return False

    try:
        await websocket.send(
            json.dumps(
                payload,
                ensure_ascii=False
            )
        )
        return True

    except Exception as error:
        print("[SEND ERROR]", error)
        return False


# =========================================================
# REMOVE CONNECTION
# =========================================================

def remove_connection(websocket):
    info = websocket_info.pop(
        websocket,
        None
    )

    if not info:
        return None

    room_id = str(
        info.get("room_id", "")
    )

    role = info.get(
        "role"
    )

    viewer_id = info.get(
        "viewer_id"
    )

    room = rooms.get(
        room_id
    )

    if room is None:
        return info

    if role == "host":

        if room.get("host") is websocket:
            room["host"] = None

    elif role == "viewer":

        viewers = room.get(
            "viewers",
            {}
        )

        if viewer_id in viewers:

            if viewers[viewer_id] is websocket:
                del viewers[viewer_id]

    if (
        room.get("host") is None
        and not room.get("viewers")
    ):
        rooms.pop(
            room_id,
            None
        )

    return info


# =========================================================
# JOIN
# =========================================================

async def handle_join(
    websocket,
    message
):
    room_id = str(
        message.get(
            "room_id",
            ""
        )
    ).strip()

    role = str(
        message.get(
            "role",
            ""
        )
    ).strip().lower()

    if not room_id:

        await send_json(
            websocket,
            {
                "type": "error",
                "message": "room_id is required"
            }
        )

        return

    if role not in (
        "host",
        "viewer"
    ):

        await send_json(
            websocket,
            {
                "type": "error",
                "message": "role must be host or viewer"
            }
        )

        return

    room = rooms[
        room_id
    ]

    # =====================================================
    # HOST
    # =====================================================

    if role == "host":

        old_host = room.get(
            "host"
        )

        if (
            old_host is not None
            and old_host is not websocket
        ):

            await send_json(
                old_host,
                {
                    "type": "host-replaced"
                }
            )

            try:
                await old_host.close()
            except Exception:
                pass

            websocket_info.pop(
                old_host,
                None
            )

        room["host"] = websocket

        websocket_info[
            websocket
        ] = {
            "room_id": room_id,
            "role": "host",
            "viewer_id": None
        }

        await send_json(
            websocket,
            {
                "type": "joined",
                "room_id": room_id,
                "role": "host"
            }
        )

        # Inform existing viewers
        for viewer_id, viewer in list(
            room["viewers"].items()
        ):

            await send_json(
                viewer,
                {
                    "type": "host-present",
                    "viewer_id": viewer_id
                }
            )

        print(
            f"[HOST JOIN] room={room_id}"
        )

        return

    # =====================================================
    # VIEWER
    # =====================================================

    viewer_id = uuid.uuid4().hex[:12]

    room["viewers"][
        viewer_id
    ] = websocket

    websocket_info[
        websocket
    ] = {
        "room_id": room_id,
        "role": "viewer",
        "viewer_id": viewer_id
    }

    host = room.get(
        "host"
    )

    await send_json(
        websocket,
        {
            "type": "joined",
            "room_id": room_id,
            "role": "viewer",
            "viewer_id": viewer_id,
            "host_present": host is not None
        }
    )

    if host is not None:

        await send_json(
            websocket,
            {
                "type": "host-present",
                "viewer_id": viewer_id
            }
        )

        await send_json(
            host,
            {
                "type": "viewer-joined",
                "viewer_id": viewer_id
            }
        )

    else:

        await send_json(
            websocket,
            {
                "type": "host-not-present",
                "viewer_id": viewer_id
            }
        )

    print(
        f"[VIEWER JOIN] room={room_id} viewer={viewer_id}"
    )


# =========================================================
# WEBRTC ROUTING
# =========================================================

async def route_webrtc_message(
    websocket,
    message
):
    info = websocket_info.get(
        websocket
    )

    if not info:
        return

    room_id = str(
        info.get(
            "room_id",
            ""
        )
    )

    role = info.get(
        "role"
    )

    sender_viewer_id = info.get(
        "viewer_id"
    )

    room = rooms.get(
        room_id
    )

    if room is None:
        return

    message_type = message.get(
        "type"
    )

    # =====================================================
    # HOST -> SPECIFIC VIEWER
    # =====================================================

    if role == "host":

        viewer_id = str(
            message.get(
                "viewer_id",
                ""
            )
        ).strip()

        if not viewer_id:

            print(
                f"[WEBRTC] host {message_type} "
                f"without viewer_id"
            )

            return

        viewer = room[
            "viewers"
        ].get(
            viewer_id
        )

        if viewer is None:
            return

        payload = dict(
            message
        )

        payload["from_role"] = "host"
        payload["viewer_id"] = viewer_id

        await send_json(
            viewer,
            payload
        )

        return

    # =====================================================
    # VIEWER -> HOST
    # =====================================================

    if role == "viewer":

        host = room.get(
            "host"
        )

        if host is None:
            return

        payload = dict(
            message
        )

        payload["from_role"] = "viewer"
        payload["viewer_id"] = sender_viewer_id

        await send_json(
            host,
            payload
        )


# =========================================================
# ROOM INFO
# =========================================================

async def handle_room_info(
    websocket
):
    info = websocket_info.get(
        websocket
    )

    if not info:
        return

    room_id = str(
        info.get(
            "room_id",
            ""
        )
    )

    room = rooms.get(
        room_id
    )

    if room is None:

        await send_json(
            websocket,
            {
                "type": "room-info",
                "host_present": False,
                "viewer_count": 0
            }
        )

        return

    await send_json(
        websocket,
        {
            "type": "room-info",
            "host_present":
                room.get("host") is not None,
            "viewer_count":
                len(
                    room.get(
                        "viewers",
                        {}
                    )
                )
        }
    )


# =========================================================
# PING
# =========================================================

async def handle_ping(
    websocket
):
    await send_json(
        websocket,
        {
            "type": "pong"
        }
    )


# =========================================================
# LEAVE
# =========================================================

async def handle_leave(
    websocket
):
    info = websocket_info.get(
        websocket
    )

    if not info:
        return

    room_id = str(
        info.get(
            "room_id",
            ""
        )
    )

    role = info.get(
        "role"
    )

    viewer_id = info.get(
        "viewer_id"
    )

    room = rooms.get(
        room_id
    )

    if room is None:
        return

    # Viewer leaving
    if (
        role == "viewer"
        and viewer_id
    ):

        host = room.get(
            "host"
        )

        if host is not None:

            await send_json(
                host,
                {
                    "type": "viewer-left",
                    "viewer_id": viewer_id
                }
            )

    # Host leaving
    elif role == "host":

        for current_viewer_id, viewer in list(
            room.get(
                "viewers",
                {}
            ).items()
        ):

            await send_json(
                viewer,
                {
                    "type": "host-left",
                    "viewer_id": current_viewer_id
                }
            )


# =========================================================
# CLIENT HANDLER
# =========================================================

async def client_handler(
    websocket
):
    print("[CONNECT]")

    try:

        async for raw_message in websocket:

            try:

                message = json.loads(
                    raw_message
                )

            except json.JSONDecodeError:

                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "invalid JSON"
                    }
                )

                continue

            message_type = message.get(
                "type"
            )

            # -------------------------------------------------
            # JOIN
            # -------------------------------------------------

            if message_type == "join":

                await handle_join(
                    websocket,
                    message
                )

                continue

            # -------------------------------------------------
            # WEBRTC
            # -------------------------------------------------

            if message_type in (
                "offer",
                "answer",
                "ice-candidate",
                "candidate",
                "ice"
            ):

                await route_webrtc_message(
                    websocket,
                    message
                )

                continue

            # -------------------------------------------------
            # ROOM INFO
            # -------------------------------------------------

            if message_type == "room-info":

                await handle_room_info(
                    websocket
                )

                continue

            # -------------------------------------------------
            # PING
            # -------------------------------------------------

            if message_type == "ping":

                await handle_ping(
                    websocket
                )

                continue

            # -------------------------------------------------
            # LEAVE
            # -------------------------------------------------

            if message_type == "leave":

                await handle_leave(
                    websocket
                )

                remove_connection(
                    websocket
                )

                continue

            # -------------------------------------------------
            # NEGOTIATION NEEDED
            # -------------------------------------------------

            if message_type == "negotiationneeded":

                await route_webrtc_message(
                    websocket,
                    message
                )

                continue

            # -------------------------------------------------
            # UNKNOWN
            # -------------------------------------------------

            await send_json(
                websocket,
                {
                    "type": "error",
                    "message":
                        "unknown message type"
                }
            )

    except websockets.exceptions.ConnectionClosed:
        pass

    except Exception as error:

        print(
            "[CLIENT ERROR]",
            repr(error)
        )

    finally:

        info = websocket_info.get(
            websocket
        )

        if info:

            room_id = str(
                info.get(
                    "room_id",
                    ""
                )
            )

            role = info.get(
                "role"
            )

            viewer_id = info.get(
                "viewer_id"
            )

            room = rooms.get(
                room_id
            )

            if room is not None:

                # Viewer disconnected
                if (
                    role == "viewer"
                    and viewer_id
                ):

                    host = room.get(
                        "host"
                    )

                    if host is not None:

                        await send_json(
                            host,
                            {
                                "type":
                                    "viewer-left",
                                "viewer_id":
                                    viewer_id
                            }
                        )

                # Host disconnected
                elif role == "host":

                    for current_viewer_id, viewer in list(
                        room.get(
                            "viewers",
                            {}
                        ).items()
                    ):

                        await send_json(
                            viewer,
                            {
                                "type":
                                    "host-left",
                                "viewer_id":
                                    current_viewer_id
                            }
                        )

        remove_connection(
            websocket
        )

        print("[DISCONNECT]")


# =========================================================
# MAIN
# =========================================================

async def main():

    print("=" * 45)
    print("LainoLive Signaling Server")
    print("=" * 45)
    print(
        f"Listening on {HOST}:{PORT}"
    )

    async with websockets.serve(
        client_handler,
        HOST,
        PORT,
        max_size=1024 * 1024,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=10
    ):
        await asyncio.Future()


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "Server stopped."
        )
