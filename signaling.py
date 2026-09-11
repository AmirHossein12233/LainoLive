import asyncio
import json
import os
import uuid
from collections import defaultdict

import websockets


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "10000"))

rooms = defaultdict(
    lambda: {
        "host": None,
        "viewers": {}
    }
)

websocket_info = {}


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
        print("[SEND ERROR]", repr(error))
        return False


async def broadcast_room_info(room_id):
    room = rooms.get(room_id)

    if room is None:
        return

    host = room.get("host")
    viewers = room.get("viewers", {})

    payload = {
        "type": "room-info",
        "room_id": str(room_id),
        "host_present": host is not None,
        "viewer_count": len(viewers)
    }

    if host is not None:
        await send_json(
            host,
            payload
        )

    for viewer in list(viewers.values()):
        await send_json(
            viewer,
            payload
        )


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

    role = info.get("role")
    viewer_id = info.get("viewer_id")

    room = rooms.get(room_id)

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

    if role not in ("host", "viewer"):

        await send_json(
            websocket,
            {
                "type": "error",
                "message": "role must be host or viewer"
            }
        )

        return

    room = rooms[room_id]

    if role == "host":

        old_host = room.get("host")

        if (
            old_host is not None
            and old_host is not websocket
        ):

            try:
                await send_json(
                    old_host,
                    {
                        "type": "host-replaced"
                    }
                )

                await old_host.close()

            except Exception:
                pass

            websocket_info.pop(
                old_host,
                None
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
                "room_id": room_id,
                "role": "host"
            }
        )

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

        await broadcast_room_info(
            room_id
        )

        print(
            f"[HOST JOIN] room={room_id}"
        )

        return

    viewer_id = uuid.uuid4().hex[:12]

    room["viewers"][viewer_id] = websocket

    websocket_info[websocket] = {
        "room_id": room_id,
        "role": "viewer",
        "viewer_id": viewer_id
    }

    host = room.get("host")

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

    await broadcast_room_info(
        room_id
    )

    print(
        f"[VIEWER JOIN] room={room_id} viewer={viewer_id}"
    )


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

    role = info.get("role")
    sender_viewer_id = info.get("viewer_id")

    room = rooms.get(room_id)

    if room is None:
        return

    if role == "host":

        viewer_id = str(
            message.get(
                "viewer_id",
                ""
            )
        ).strip()

        if not viewer_id:
            return

        viewer = room.get(
            "viewers",
            {}
        ).get(
            viewer_id
        )

        if viewer is None:
            return

        payload = dict(message)

        payload["from_role"] = "host"
        payload["viewer_id"] = viewer_id

        await send_json(
            viewer,
            payload
        )

        return

    if role == "viewer":

        host = room.get("host")

        if host is None:
            return

        payload = dict(message)

        payload["from_role"] = "viewer"
        payload["viewer_id"] = sender_viewer_id

        await send_json(
            host,
            payload
        )


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

    role = info.get("role")
    viewer_id = info.get("viewer_id")

    room = rooms.get(room_id)

    if room is None:
        return

    if (
        role == "viewer"
        and viewer_id
    ):

        host = room.get("host")

        if host is not None:

            await send_json(
                host,
                {
                    "type": "viewer-left",
                    "viewer_id": viewer_id
                }
            )

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


async def client_handler(websocket):

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

            if message_type == "join":

                await handle_join(
                    websocket,
                    message
                )

                continue

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

            if message_type == "room-info":

                info = websocket_info.get(
                    websocket
                )

                if info:

                    await broadcast_room_info(
                        str(
                            info.get(
                                "room_id",
                                ""
                            )
                        )
                    )

                continue

            if message_type == "ping":

                await send_json(
                    websocket,
                    {
                        "type": "pong"
                    }
                )

                continue

            if message_type == "leave":

                room_id = str(
                    websocket_info.get(
                        websocket,
                        {}
                    ).get(
                        "room_id",
                        ""
                    )
                )

                await handle_leave(
                    websocket
                )

                remove_connection(
                    websocket
                )

                if room_id:
                    await broadcast_room_info(
                        room_id
                    )

                continue

            if message_type == "negotiationneeded":

                await route_webrtc_message(
                    websocket,
                    message
                )

                continue

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

        room_id = ""

        if info:

            room_id = str(
                info.get(
                    "room_id",
                    ""
                )
            )

            role = info.get("role")
            viewer_id = info.get("viewer_id")

            room = rooms.get(room_id)

            if room is not None:

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

        if room_id:
            await broadcast_room_info(
                room_id
            )

        print("[DISCONNECT]")


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