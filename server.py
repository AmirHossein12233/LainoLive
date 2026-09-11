from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid



app = FastAPI(
    title="LainoLive API"
)



app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)





# =========================
# Storage
# =========================

streams = {}

chat_rooms = {}

webrtc_rooms = {}






# =========================
# Models
# =========================


class StartStream(BaseModel):

    title: str = "LainoLive"

    username: str = "guest"

    videoQuality: Optional[str] = "720"

    audioQuality: Optional[str] = "128000"





class StopStream(BaseModel):

    stream_id: str






class ViewerData(BaseModel):

    stream_id: str







# =========================
# Basic
# =========================


@app.get("/")
def home():

    return {

        "app":"LainoLive",

        "status":"online"

    }





@app.get("/health")
def health():

    return {

        "status":"ok",

        "time":

            datetime.now().isoformat()

    }








# =========================
# Streams
# =========================


@app.post("/api/streams/start")
def start_stream(
    data: StartStream
):


    stream_id = str(
        uuid.uuid4()
    )



    stream = {


        "id":

            stream_id,


        "title":

            data.title,


        "username":

            data.username,


        "videoQuality":

            data.videoQuality,


        "audioQuality":

            data.audioQuality,


        "viewers":

            0,


        "started":

            datetime.now().isoformat()

    }




    streams[stream_id] = stream




    return {


        "success":

            True,


        "stream_id":

            stream_id,


        "stream":

            stream

    }









@app.get("/api/streams")
def list_streams():


    return {


        "success":

            True,


        "streams":

            list(streams.values())

    }









@app.get("/api/streams/{stream_id}")
def get_stream(
    stream_id:str
):


    if stream_id not in streams:


        return {


            "success":

                False

        }



    return {


        "success":

            True,


        "stream":

            streams[stream_id]

    }









@app.post("/api/streams/stop")
def stop_stream(
    data:StopStream
):


    if data.stream_id in streams:


        del streams[data.stream_id]



        return {


            "success":

                True,


            "message":

                "stream stopped"

        }




    return {


        "success":

            False

    }








# =========================
# Viewers
# =========================


@app.post("/api/streams/viewer/join")
def join_viewer(
    data:ViewerData
):


    if data.stream_id in streams:


        streams[data.stream_id]["viewers"] += 1



        return {


            "success":

                True,


            "viewers":

                streams[data.stream_id]["viewers"]

        }



    return {


        "success":

            False

    }









@app.post("/api/streams/viewer/leave")
def leave_viewer(
    data:ViewerData
):


    if data.stream_id in streams:


        if streams[data.stream_id]["viewers"] > 0:

            streams[data.stream_id]["viewers"] -= 1




        return {


            "success":

                True

        }



    return {


        "success":

            False

    }









# =========================
# Chat WebSocket
# =========================


@app.websocket("/ws/chat/{stream_id}")
async def chat_socket(
    websocket:WebSocket,
    stream_id:str
):


    await websocket.accept()



    if stream_id not in chat_rooms:

        chat_rooms[stream_id] = []



    chat_rooms[stream_id].append(
        websocket
    )



    try:


        while True:


            data = await websocket.receive_json()



            for client in chat_rooms[stream_id]:


                await client.send_json(
                    data
                )



    except WebSocketDisconnect:


        if websocket in chat_rooms.get(stream_id, []):


            chat_rooms[stream_id].remove(
                websocket
            )









# =========================
# WebRTC Signaling
# =========================


@app.websocket("/ws/webrtc/{stream_id}")
async def webrtc_socket(
    websocket:WebSocket,
    stream_id:str
):


    await websocket.accept()



    if stream_id not in webrtc_rooms:

        webrtc_rooms[stream_id] = []



    webrtc_rooms[stream_id].append(
        websocket
    )



    try:


        while True:


            data = await websocket.receive_json()



            for client in webrtc_rooms[stream_id]:


                if client != websocket:


                    await client.send_json(
                        data
                    )



    except WebSocketDisconnect:


        if websocket in webrtc_rooms.get(stream_id, []):


            webrtc_rooms[stream_id].remove(
                websocket
            )