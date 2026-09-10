import asyncio
import json
import os

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8001"))


# =========================================================
# ROOM STRUCTURE
# =========================================================
#
# rooms = {
#     "stream_id": {
#         "clients": {
#             websocket: {
#                 "username": "...",
#                 "role": "owner" / "viewer",
#                 "peer_id": "..."
#             }
#         }
#     }
# }
#

rooms = {}
rooms_lock = asyncio.Lock()


# =========================================================
# JSON
# =========================================================

def make_message(data):
    return json.dumps(
        data,
        ensure_ascii=False
    )


async def send_json(websocket, data):
    try:
        await websocket.send(
            make_message(data)
        )
        return True

    except Exception:
        return False


# =========================================================
# ROOM HELPERS
# =========================================================

async def add_client(
    room_id,
    websocket,
    username,
    role
):
    async with rooms_lock:

        room = rooms.setdefault(
            room_id,
            {
                "clients": {}
            }
        )

        peer_id = (
            f"{role}:{username}:"
            f"{id(websocket)}"
        )

        room["clients"][websocket] = {
            "username": username,
            "role": role,
            "peer_id": peer_id
        }

        return peer_id


async def remove_client(
    room_id,
    websocket
):
    async with rooms_lock:

        room = rooms.get(room_id)

        if room is None:
            return None

        client = room["clients"].pop(
            websocket,
            None
        )

        if not room["clients"]:
            rooms.pop(
                room_id,
                None
            )

        return client


async def get_clients(room_id):
    async with rooms_lock:

        room = rooms.get(room_id)

        if room is None:
            return []

        return [
            (
                websocket,
                info.copy()
            )
            for websocket, info
            in room["clients"].items()
        ]


async def find_client_by_peer_id(
    room_id,
    peer_id
):
    async with rooms_lock:

        room = rooms.get(room_id)

        if room is None:
            return None

        for websocket, info in room["clients"].items():

            if info.get("peer_id") == peer_id:
                return websocket

        return None


# =========================================================
# BROADCAST PEER EVENT
# =========================================================

async def send_peer_event(
    room_id,
    sender_websocket,
    event
):
    clients = await get_clients(
        room_id
    )

    sender_info = None

    for websocket, info in clients:
        if websocket is sender_websocket:
            sender_info = info
            break

    if sender_info is None:
        return

    payload = {
        "type": event,
        "username": sender_info["username"],
        "role": sender_info["role"],
        "peer_id": sender_info["peer_id"]
    }

    for websocket, info in clients:

        if websocket is sender_websocket:
            continue

        await send_json(
            websocket,
            payload
        )


# =========================================================
# ROUTE SIGNAL
# =========================================================

async def route_signal(
    room_id,
    sender_websocket,
    message
):
    clients = await get_clients(
        room_id
    )

    sender_info = None

    for websocket, info in clients:

        if websocket is sender_websocket:

            sender_info = info
            break

    if sender_info is None:
        return


    target_peer_id = str(
        message.get(
            "target_peer_id",
            ""
        )
    ).strip()


    target_username = str(
        message.get(
            "target_username",
            ""
        )
    ).strip()


    target_websocket = None


    # -----------------------------------------------------
    # 1. پیدا کردن بر اساس peer_id
    # -----------------------------------------------------

    if target_peer_id:

        target_websocket = (
            await find_client_by_peer_id(
                room_id,
                target_peer_id
            )
        )


    # -----------------------------------------------------
    # 2. سازگاری با username
    # -----------------------------------------------------

    if (
        target_websocket is None
        and target_username
    ):

        for websocket, info in clients:

            if (
                info.get("username")
                == target_username
            ):
                target_websocket = websocket
                break


    # -----------------------------------------------------
    # 3. اگر مقصد پیدا نشد
    # -----------------------------------------------------

    if target_websocket is None:

        await send_json(
            sender_websocket,
            {
                "type": "error",
                "message": (
                    "Peer مقصد پیدا نشد."
                )
            }
        )

        return


    outgoing = dict(message)

    outgoing["username"] = (
        sender_info["username"]
    )

    outgoing["role"] = (
        sender_info["role"]
    )

    outgoing["peer_id"] = (
        sender_info["peer_id"]
    )


    await send_json(
        target_websocket,
        outgoing
    )


# =========================================================
# CONNECTION
# =========================================================

async def handle_connection(
    websocket
):
    room_id = None
    username = "کاربر"
    role = "viewer"
    peer_id = None

    try:

        # -------------------------------------------------
        # اولین پیام
        # -------------------------------------------------

        raw = await websocket.recv()

        try:

            message = json.loads(
                raw
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):

            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": (
                        "پیام JSON نامعتبر است."
                    )
                }
            )

            return


        if (
            message.get("type")
            != "join"
        ):

            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": (
                        "ابتدا باید join ارسال شود."
                    )
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
        ).strip()


        role = str(
            message.get(
                "role",
                "viewer"
            )
        ).strip()


        if not room_id:

            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": (
                        "شناسه لایو مشخص نشده است."
                    )
                }
            )

            return


        if not username:
            username = "کاربر"


        if role not in {
            "owner",
            "viewer"
        }:

            role = "viewer"


        # -------------------------------------------------
        # ADD CLIENT
        # -------------------------------------------------

        peer_id = await add_client(
            room_id,
            websocket,
            username,
            role
        )


        clients = await get_clients(
            room_id
        )


        print(
            f"[JOIN] room={room_id} "
            f"user={username} "
            f"role={role} "
            f"peer={peer_id} "
            f"clients={len(clients)}"
        )


        # -------------------------------------------------
        # JOINED
        # -------------------------------------------------

        await send_json(
            websocket,
            {
                "type": "joined",
                "room_id": room_id,
                "username": username,
                "role": role,
                "peer_id": peer_id,
                "users_count": len(clients)
            }
        )


        # -------------------------------------------------
        # اطلاع ورود به دیگران
        # -------------------------------------------------

        await send_peer_event(
            room_id,
            websocket,
            "peer_joined"
        )


        # -------------------------------------------------
        # برای viewer:
        # اطلاعات owner را بفرست
        # -------------------------------------------------

        if role == "viewer":

            for client_websocket, info in clients:

                if (
                    info.get("role")
                    == "owner"
                ):

                    await send_json(
                        websocket,
                        {
                            "type":
                                "owner_available",

                            "username":
                                info.get(
                                    "username"
                                ),

                            "peer_id":
                                info.get(
                                    "peer_id"
                                ),

                            "role":
                                "owner"
                        }
                    )

                    break


        # -------------------------------------------------
        # RECEIVE
        # -------------------------------------------------

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
                        "message": (
                            "پیام JSON نامعتبر است."
                        )
                    }
                )

                continue


            message_type = str(
                message.get(
                    "type",
                    ""
                )
            ).strip()


            # -------------------------------------------------
            # PING
            # -------------------------------------------------

            if message_type == "ping":

                await send_json(
                    websocket,
                    {
                        "type": "pong"
                    }
                )

                continue


            # -------------------------------------------------
            # فقط پیام‌های WebRTC
            # -------------------------------------------------

            allowed_types = {
                "offer",
                "answer",
                "ice-candidate"
            }


            if (
                message_type
                not in allowed_types
            ):

                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": (
                            "نوع پیام WebRTC "
                            "نامعتبر است."
                        )
                    }
                )

                continue


            # -------------------------------------------------
            # Route
            # -------------------------------------------------

            message["room_id"] = room_id


            await route_signal(
                room_id,
                websocket,
                message
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

            removed_client = (
                await remove_client(
                    room_id,
                    websocket
                )
            )


            if removed_client is not None:

                print(
                    f"[LEAVE] "
                    f"room={room_id} "
                    f"user="
                    f"{removed_client.get('username')} "
                    f"peer="
                    f"{removed_client.get('peer_id')}"
                )


                clients = await get_clients(
                    room_id
                )


                payload = {
                    "type": "peer_left",
                    "username":
                        removed_client.get(
                            "username"
                        ),
                    "role":
                        removed_client.get(
                            "role"
                        ),
                    "peer_id":
                        removed_client.get(
                            "peer_id"
                        )
                }


                for client_websocket, info in clients:

                    await send_json(
                        client_websocket,
                        payload
                    )


# =========================================================
# SERVER
# =========================================================

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
        "Routing: TARGETED"
    )

    print(
        "Multiple viewers: ENABLED"
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


# =========================================================
# START
# =========================================================

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
