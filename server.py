import os
import uuid
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="LainoLive Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StreamInfo(BaseModel):
    stream_id: str
    username: str
    title: str = ""
    is_live: bool = True


class RTCClient:
    def __init__(
        self,
        websocket: WebSocket,
        client_id: str,
        role: str,
        username: Optional[str] = None,
    ):
        self.websocket = websocket
        self.client_id = client_id
        self.role = role
        self.username = username


streams: Dict[str, StreamInfo] = {}
rtc_rooms: Dict[str, Dict[str, RTCClient]] = {}


def ensure_room(stream_id: str) -> None:
    rtc_rooms.setdefault(stream_id, {})


def remove_client(stream_id: str, client_id: str) -> None:
    room = rtc_rooms.get(stream_id)

    if not room:
        return

    room.pop(client_id, None)

    if not room:
        rtc_rooms.pop(stream_id, None)


def viewer_count(stream_id: str) -> int:
    room = rtc_rooms.get(stream_id, {})
    return sum(
        1
        for client in room.values()
        if client.role == "viewer"
    )


def broadcaster_count(stream_id: str) -> int:
    room = rtc_rooms.get(stream_id, {})
    return sum(
        1
        for client in room.values()
        if client.role == "broadcaster"
    )


async def send_json_safe(
    websocket: WebSocket,
    data: dict,
) -> bool:
    try:
        await websocket.send_json(data)
        return True
    except Exception:
        return False


async def send_to_role(
    stream_id: str,
    role: str,
    data: dict,
    exclude_client_id: Optional[str] = None,
) -> None:
    room = rtc_rooms.get(stream_id, {})
    dead = []

    for client_id, client in list(room.items()):
        if client.role != role:
            continue

        if (
            exclude_client_id
            and client_id == exclude_client_id
        ):
            continue

        ok = await send_json_safe(
            client.websocket,
            data,
        )

        if not ok:
            dead.append(client_id)

    for client_id in dead:
        remove_client(
            stream_id,
            client_id,
        )


async def broadcast_room(
    stream_id: str,
    data: dict,
    exclude_client_id: Optional[str] = None,
) -> None:
    room = rtc_rooms.get(stream_id, {})
    dead = []

    for client_id, client in list(room.items()):

        if (
            exclude_client_id
            and client_id == exclude_client_id
        ):
            continue

        ok = await send_json_safe(
            client.websocket,
            data,
        )

        if not ok:
            dead.append(client_id)

    for client_id in dead:
        remove_client(
            stream_id,
            client_id,
        )


async def notify_viewer_count(
    stream_id: str,
) -> None:
    await broadcast_room(
        stream_id,
        {
            "type": "viewer-count",
            "stream_id": stream_id,
            "count": viewer_count(stream_id),
        },
    )


@app.get("/")
async def root():
    return {
        "success": True,
        "service": "LainoLive",
        "status": "online",
    }


@app.get("/health")
async def health():
    return {
        "success": True,
        "status": "ok",
        "streams": sum(
            1
            for stream in streams.values()
            if stream.is_live
        ),
        "rtc_rooms": len(rtc_rooms),
        "viewers": sum(
            viewer_count(stream_id)
            for stream_id in rtc_rooms
        ),
    }


class StreamStartRequest(BaseModel):
    stream_id: Optional[str] = None
    username: str
    title: str = ""


@app.post("/api/streams/start")
async def start_stream(
    data: StreamStartRequest,
):
    stream_id = (
        data.stream_id
        or str(uuid.uuid4())
    )

    streams[stream_id] = StreamInfo(
        stream_id=stream_id,
        username=data.username,
        title=data.title,
        is_live=True,
    )

    ensure_room(stream_id)

    return {
        "success": True,
        "stream_id": stream_id,
        "username": data.username,
        "title": data.title,
        "message": "لایو شروع شد.",
    }


@app.get("/api/streams")
async def get_streams():
    result = []

    for stream in streams.values():

        if not stream.is_live:
            continue

        item = stream.model_dump()

        item["viewers"] = viewer_count(
            stream.stream_id
        )

        item["broadcasters"] = broadcaster_count(
            stream.stream_id
        )

        result.append(item)

    return {
        "success": True,
        "streams": result,
    }


@app.get("/api/streams/{stream_id}")
async def get_stream(
    stream_id: str,
):
    stream = streams.get(stream_id)

    if not stream:
        return {
            "success": False,
            "message": "لایو پیدا نشد.",
        }

    item = stream.model_dump()

    item["viewers"] = viewer_count(
        stream_id
    )

    item["broadcasters"] = broadcaster_count(
        stream_id
    )

    return {
        "success": True,
        "stream": item,
    }


class StreamStopRequest(BaseModel):
    stream_id: str
    username: str


@app.post("/api/streams/stop")
async def stop_stream(
    data: StreamStopRequest,
):
    stream = streams.get(
        data.stream_id
    )

    if not stream:
        return {
            "success": False,
            "message": "لایو پیدا نشد.",
        }

    if stream.username != data.username:
        return {
            "success": False,
            "message":
                "کاربر مجاز به پایان این لایو نیست.",
        }

    stream.is_live = False

    await broadcast_room(
        data.stream_id,
        {
            "type": "stream-ended",
            "stream_id": data.stream_id,
        },
    )

    rtc_rooms.pop(
        data.stream_id,
        None,
    )

    return {
        "success": True,
        "message": "لایو پایان یافت.",
    }


@app.websocket(
    "/ws/viewer/{stream_id}"
)
async def viewer_signaling(
    websocket: WebSocket,
    stream_id: str,
):
    await websocket.accept()

    client_id = str(
        uuid.uuid4()
    )

    ensure_room(stream_id)

    rtc_rooms[stream_id][client_id] = RTCClient(
        websocket=websocket,
        client_id=client_id,
        role="viewer",
    )

    await send_json_safe(
        websocket,
        {
            "type": "connected",
            "client_id": client_id,
            "stream_id": stream_id,
            "role": "viewer",
            "viewer_count":
                viewer_count(stream_id),
        },
    )

    await send_to_role(
        stream_id,
        "broadcaster",
        {
            "type": "viewer-ready",
            "stream_id": stream_id,
            "viewer_id": client_id,
        },
    )

    await notify_viewer_count(
        stream_id
    )

    try:

        while True:

            message = await websocket.receive_json()

            message_type = message.get(
                "type"
            )

            if message_type == "viewer-ready":

                await send_to_role(
                    stream_id,
                    "broadcaster",
                    {
                        "type":
                            "viewer-ready",

                        "stream_id":
                            stream_id,

                        "viewer_id":
                            client_id,
                    },
                )

            elif message_type in {
                "offer",
                "answer",
                "ice-candidate",
                "candidate",
            }:

                target_id = message.get(
                    "target"
                )

                payload = dict(message)

                payload["sender"] = (
                    client_id
                )

                if target_id:

                    target = (
                        rtc_rooms
                        .get(
                            stream_id,
                            {},
                        )
                        .get(
                            target_id
                        )
                    )

                    if target:

                        await send_json_safe(
                            target.websocket,
                            payload,
                        )

                else:

                    await send_to_role(
                        stream_id,
                        "broadcaster",
                        payload,
                        exclude_client_id=
                            client_id,
                    )

            else:

                target_id = message.get(
                    "target"
                )

                payload = dict(message)

                payload["sender"] = (
                    client_id
                )

                if target_id:

                    target = (
                        rtc_rooms
                        .get(
                            stream_id,
                            {},
                        )
                        .get(
                            target_id
                        )
                    )

                    if target:

                        await send_json_safe(
                            target.websocket,
                            payload,
                        )

                else:

                    await broadcast_room(
                        stream_id,
                        payload,
                        exclude_client_id=
                            client_id,
                    )

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:

        remove_client(
            stream_id,
            client_id,
        )

        await send_to_role(
            stream_id,
            "broadcaster",
            {
                "type":
                    "viewer-left",

                "stream_id":
                    stream_id,

                "viewer_id":
                    client_id,
            },
        )

        await notify_viewer_count(
            stream_id
        )


@app.websocket(
    "/ws/broadcaster/{stream_id}"
)
async def broadcaster_signaling(
    websocket: WebSocket,
    stream_id: str,
):
    await websocket.accept()

    client_id = str(
        uuid.uuid4()
    )

    ensure_room(stream_id)

    for old_id, old_client in list(
        rtc_rooms[stream_id].items()
    ):

        if old_client.role == "broadcaster":

            try:
                await old_client.websocket.close()
            except Exception:
                pass

            rtc_rooms[
                stream_id
            ].pop(
                old_id,
                None,
            )

    rtc_rooms[stream_id][client_id] = RTCClient(
        websocket=websocket,
        client_id=client_id,
        role="broadcaster",
    )

    await send_json_safe(
        websocket,
        {
            "type": "connected",
            "client_id": client_id,
            "stream_id": stream_id,
            "role": "broadcaster",
            "viewer_count":
                viewer_count(stream_id),
        },
    )

    await send_to_role(
        stream_id,
        "viewer",
        {
            "type":
                "broadcaster-ready",

            "stream_id":
                stream_id,
        },
    )

    for viewer_id, viewer in list(
        rtc_rooms
        .get(
            stream_id,
            {},
        )
        .items()
    ):

        if viewer.role != "viewer":
            continue

        await send_json_safe(
            websocket,
            {
                "type":
                    "viewer-ready",

                "stream_id":
                    stream_id,

                "viewer_id":
                    viewer_id,
            },
        )

    try:

        while True:

            message = await websocket.receive_json()

            message_type = message.get(
                "type"
            )

            if message_type in {
                "offer",
                "answer",
                "ice-candidate",
                "candidate",
            }:

                target_id = message.get(
                    "target"
                )

                payload = dict(message)

                payload["sender"] = (
                    client_id
                )

                if target_id:

                    target = (
                        rtc_rooms
                        .get(
                            stream_id,
                            {},
                        )
                        .get(
                            target_id
                        )
                    )

                    if target:

                        await send_json_safe(
                            target.websocket,
                            payload,
                        )

                else:

                    await send_to_role(
                        stream_id,
                        "viewer",
                        payload,
                        exclude_client_id=
                            client_id,
                    )

            elif message_type == "viewer-ready":

                viewer_id = message.get(
                    "viewer_id"
                )

                viewer = (
                    rtc_rooms
                    .get(
                        stream_id,
                        {},
                    )
                    .get(
                        viewer_id
                    )
                )

                if viewer:

                    await send_json_safe(
                        viewer.websocket,
                        {
                            "type":
                                "broadcaster-ready",

                            "stream_id":
                                stream_id,
                        },
                    )

            else:

                target_id = message.get(
                    "target"
                )

                payload = dict(message)

                payload["sender"] = (
                    client_id
                )

                if target_id:

                    target = (
                        rtc_rooms
                        .get(
                            stream_id,
                            {},
                        )
                        .get(
                            target_id
                        )
                    )

                    if target:

                        await send_json_safe(
                            target.websocket,
                            payload,
                        )

                else:

                    await send_to_role(
                        stream_id,
                        "viewer",
                        payload,
                        exclude_client_id=
                            client_id,
                    )

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:

        remove_client(
            stream_id,
            client_id,
        )

        await send_to_role(
            stream_id,
            "viewer",
            {
                "type":
                    "broadcaster-left",

                "stream_id":
                    stream_id,
            },
        )


@app.websocket(
    "/ws/stream/{stream_id}"
)
async def generic_stream_signaling(
    websocket: WebSocket,
    stream_id: str,
):
    await websocket.accept()

    client_id = str(
        uuid.uuid4()
    )

    ensure_room(stream_id)

    rtc_rooms[stream_id][client_id] = RTCClient(
        websocket=websocket,
        client_id=client_id,
        role="unknown",
    )

    await send_json_safe(
        websocket,
        {
            "type": "connected",
            "client_id": client_id,
            "stream_id": stream_id,
        },
    )

    try:

        while True:

            message = await websocket.receive_json()

            target_id = message.get(
                "target"
            )

            payload = dict(message)

            payload["sender"] = (
                client_id
            )

            if target_id:

                target = (
                    rtc_rooms
                    .get(
                        stream_id,
                        {},
                    )
                    .get(
                        target_id
                    )
                )

                if target:

                    await send_json_safe(
                        target.websocket,
                        payload,
                    )

            else:

                await broadcast_room(
                    stream_id,
                    payload,
                    exclude_client_id=
                        client_id,
                )

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:

        remove_client(
            stream_id,
            client_id,
        )


if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            "5000",
        )
    )

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
