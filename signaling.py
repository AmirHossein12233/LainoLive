import asyncio
import json
import os
from collections import defaultdict

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8001"))

rooms = defaultdict(set)


async def send_json(websocket, data):
    await websocket.send(
        json.dumps(
            data,
            ensure_ascii=False
        )
    )


async def broadcast(room_id, sender, data):
    clients = list(
        rooms.get(
            room_id,
            set()
        )
    )

    if not clients:
        return

    message = json.dumps(
        data,
        ensure_ascii=False
    )

    for client in clients:
        if client is sender:
            continue

        try:
            await client.send(message)
        except Exception:
            pass


async def handle_connection(websocket):
    room_id = None
    username = "کاربر"
    role = "viewer"

    try:
        # اولین پیام باید join باشد
        raw = await websocket.recv()

        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": "پیام JSON نامعتبر است."
                }
            )
            return

        if message.get("type") != "join":
            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": "ابتدا باید وارد اتاق شوید."
                }
            )
            return

        room_id = str(
            message.get(
                "room_id",
                ""
            )
        ).strip()

        username = str(
            message.get(
                "username",
                "کاربر"
            )
        ).strip() or "کاربر"

        role = str(
            message.get(
                "role",
                "viewer"
            )
        ).strip()

        if role not in {
            "owner",
            "viewer"
        }:
            role = "viewer"

        if not room_id:
            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": "شناسه اتاق مشخص نشده است."
                }
            )
            return

        # اضافه شدن به اتاق
        rooms[room_id].add(websocket)

        print(
            f"[JOIN] room={room_id} "
            f"user={username} "
            f"role={role} "
            f"clients={len(rooms[room_id])}"
        )

        await send_json(
            websocket,
            {
                "type": "joined",
                "room_id": room_id,
                "username": username,
                "role": role,
                "users_count": len(
                    rooms[room_id]
                )
            }
        )

        await broadcast(
            room_id,
            websocket,
            {
                "type": "peer_joined",
                "username": username,
                "role": role
            }
        )

        # دریافت پیام‌های بعدی
        async for raw_message in websocket:

            try:
                message = json.loads(
                    raw_message
                )
            except (json.JSONDecodeError, TypeError):
                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "پیام JSON نامعتبر است."
                    }
                )
                continue

            message_type = str(
                message.get(
                    "type",
                    ""
                )
            ).strip()

            if message_type == "ping":
                await send_json(
                    websocket,
                    {
                        "type": "pong"
                    }
                )
                continue

            allowed_types = {
                "offer",
                "answer",
                "ice-candidate"
            }

            if message_type not in allowed_types:
                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": (
                            "نوع پیام WebRTC نامعتبر است."
                        )
                    }
                )
                continue

            outgoing = dict(message)

            outgoing["room_id"] = room_id
            outgoing["username"] = username
            outgoing["role"] = role

            await broadcast(
                room_id,
                websocket,
                outgoing
            )

    except ConnectionClosed:
        pass

    except Exception as error:
        print(
            "[ERROR]",
            repr(error)
        )

    finally:
        if room_id is not None:

            clients = rooms.get(
                room_id
            )

            if clients is not None:

                clients.discard(
                    websocket
                )

                print(
                    f"[LEAVE] room={room_id} "
                    f"user={username}"
                )

                await broadcast(
                    room_id,
                    websocket,
                    {
                        "type": "peer_left",
                        "username": username,
                        "role": role
                    }
                )

                if not clients:
                    rooms.pop(
                        room_id,
                        None
                    )


async def main():
    print("=" * 60)
    print("LainoLive WebRTC Signaling")
    print("=" * 60)

    print(
        f"Host: {HOST}"
    )

    print(
        f"Port: {PORT}"
    )

    print(
        "Status: ONLINE"
    )

    print("=" * 60)

    async with serve(
        handle_connection,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        max_size=1024 * 1024
    ):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(
            main()
        )
    except KeyboardInterrupt:
        print()
        print(
            "LainoLive signaling stopped."
        )
