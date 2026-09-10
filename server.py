import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# =========================================================
# تنظیمات
# =========================================================

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))

BASE_DIR = Path(__file__).resolve().parent

USERS_FILE = BASE_DIR / "users.json"
HISTORY_FILE = BASE_DIR / "streams_history.json"

MAX_MESSAGE_LENGTH = 500
MAX_CHAT_MESSAGES = 200

PASSWORD_ITERATIONS = 310_000

users_lock = threading.Lock()
streams_lock = threading.Lock()
chat_lock = threading.Lock()
history_lock = threading.Lock()

streams = {}
chat_messages = {}
stream_history = []

next_stream_id = 1
next_chat_id = 1


# =========================================================
# JSON RESPONSE
# =========================================================

def send_json(handler, status_code, data):
    body = json.dumps(
        data,
        ensure_ascii=False
    ).encode("utf-8")

    handler.send_response(status_code)

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    handler.send_header(
        "Content-Length",
        str(len(body))
    )

    handler.send_header(
        "Cache-Control",
        "no-store"
    )

    handler.send_header(
        "Access-Control-Allow-Origin",
        "*"
    )

    handler.send_header(
        "Access-Control-Allow-Methods",
        "GET, POST, OPTIONS"
    )

    handler.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type"
    )

    handler.end_headers()

    handler.wfile.write(body)


# =========================================================
# READ JSON
# =========================================================

def read_json(handler):
    try:
        length = int(
            handler.headers.get(
                "Content-Length",
                "0"
            )
        )
    except ValueError:
        return {}

    if length <= 0:
        return {}

    if length > 1_000_000:
        return {}

    try:
        raw = handler.rfile.read(length)

        return json.loads(
            raw.decode("utf-8")
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError
    ):
        return {}


# =========================================================
# HELPERS
# =========================================================

def clean_text(
    value,
    max_length=500
):
    value = str(
        value or ""
    ).strip()

    return value[:max_length]


def clean_username(value):
    username = str(
        value or ""
    ).strip()

    return username[:30]


def valid_username(username):

    if not username:
        return False

    if (
        len(username) < 3
        or len(username) > 30
    ):
        return False

    for char in username:

        if not (
            char.isalnum()
            or char in "_-"
            or "\u0600" <= char <= "\u06ff"
        ):
            return False

    return True


def valid_password(password):

    return (
        isinstance(
            password,
            str
        )
        and 6 <= len(password) <= 128
    )


# =========================================================
# PASSWORD
# =========================================================

def hash_password(
    password,
    salt=None
):

    if salt is None:
        salt = secrets.token_bytes(16)

    password_hash = (
        hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS
        )
    )

    return {
        "salt":
            salt.hex(),

        "hash":
            password_hash.hex(),

        "iterations":
            PASSWORD_ITERATIONS
    }


def verify_password(
    password,
    record
):

    try:

        salt = bytes.fromhex(
            record["salt"]
        )

        expected = bytes.fromhex(
            record["hash"]
        )

        iterations = int(
            record.get(
                "iterations",
                PASSWORD_ITERATIONS
            )
        )

        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations
        )

        return hmac.compare_digest(
            actual,
            expected
        )

    except (
        KeyError,
        ValueError,
        TypeError
    ):

        return False


# =========================================================
# USERS
# =========================================================

def load_users():

    if not USERS_FILE.exists():

        default_username = os.getenv(
            "DEFAULT_USERNAME",
            "admin"
        ).strip()

        default_password = os.getenv(
            "DEFAULT_PASSWORD",
            "123456"
        )

        users_data = {
            default_username: {
                **hash_password(
                    default_password
                ),
                "created_at":
                    int(time.time())
            }
        }

        save_users(
            users_data
        )

        return users_data

    try:

        data = json.loads(
            USERS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            data,
            dict
        ):
            return data

        return {}

    except (
        OSError,
        json.JSONDecodeError
    ):

        return {}


def save_users(users_data):

    temporary = (
        USERS_FILE.with_suffix(
            ".tmp"
        )
    )

    temporary.write_text(
        json.dumps(
            users_data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    temporary.replace(
        USERS_FILE
    )


users = load_users()


# =========================================================
# STREAM HISTORY
# =========================================================

def load_stream_history():

    if not HISTORY_FILE.exists():
        return []

    try:

        data = json.loads(
            HISTORY_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            data,
            list
        ):
            return data

        return []

    except (
        OSError,
        json.JSONDecodeError
    ):

        return []


def save_stream_history():

    temporary = (
        HISTORY_FILE.with_suffix(
            ".tmp"
        )
    )

    temporary.write_text(
        json.dumps(
            stream_history,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    temporary.replace(
        HISTORY_FILE
    )


stream_history = load_stream_history()


# =========================================================
# NEXT STREAM ID
# =========================================================

def initialize_next_stream_id():

    highest_id = 0

    with history_lock:

        for item in stream_history:

            try:

                value = int(
                    str(
                        item.get(
                            "id",
                            "0"
                        )
                    )
                )

                if value > highest_id:
                    highest_id = value

            except (
                ValueError,
                TypeError
            ):

                continue

    return highest_id + 1


next_stream_id = initialize_next_stream_id()


# =========================================================
# STREAM PUBLIC DATA
# =========================================================

def stream_public_data(stream):

    return {
        "id":
            stream["id"],

        "title":
            stream["title"],

        "username":
            stream["username"],

        "created_at":
            stream["created_at"],

        "viewer_count":
            stream["viewer_count"]
    }


# =========================================================
# STREAM HISTORY DATA
# =========================================================

def history_public_data(stream):

    return {
        "id":
            stream["id"],

        "title":
            stream["title"],

        "username":
            stream["username"],

        "created_at":
            stream["created_at"],

        "started_at":
            stream.get(
                "started_at",
                stream["created_at"]
            ),

        "ended_at":
            stream.get(
                "ended_at"
            ),

        "duration_seconds":
            stream.get(
                "duration_seconds",
                0
            ),

        "viewer_peak":
            stream.get(
                "viewer_peak",
                0
            ),

        "viewer_count":
            stream.get(
                "viewer_count",
                0
            )
    }


# =========================================================
# HTTP HANDLER
# =========================================================

class LainoHandler(
    BaseHTTPRequestHandler
):

    # -----------------------------------------------------
    # LOG
    # -----------------------------------------------------

    def log_message(
        self,
        format_string,
        *args
    ):

        print(
            f"{self.address_string()} - "
            f"{format_string % args}"
        )

    # -----------------------------------------------------
    # OPTIONS
    # -----------------------------------------------------

    def do_OPTIONS(self):

        self.send_response(
            204
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def do_GET(self):

        path = self.path.split(
            "?",
            1
        )[0]

        # HEALTH
        if path == "/health":

            return send_json(
                self,
                200,
                {
                    "status":
                        "ok",

                    "service":
                        "LainoLive",

                    "live":
                        True,

                    "chat":
                        True
                }
            )

        # STATUS
        if path == "/api/status":

            with streams_lock:

                stream_count = len(
                    streams
                )

            with history_lock:

                history_count = len(
                    stream_history
                )

            return send_json(
                self,
                200,
                {
                    "success":
                        True,

                    "online":
                        True,

                    "streams":
                        stream_count,

                    "history":
                        history_count
                }
            )

        # ACTIVE STREAMS
        if path == "/api/streams":

            with streams_lock:

                result = [
                    stream_public_data(
                        stream
                    )
                    for stream
                    in streams.values()
                ]

            result.sort(
                key=lambda item:
                    item["created_at"],
                reverse=True
            )

            return send_json(
                self,
                200,
                {
                    "success":
                        True,

                    "streams":
                        result
                }
            )

        # STREAM HISTORY
        if path == "/api/streams/history":

            return self.get_stream_history()

        # CHAT
        if path == "/api/chat/messages":

            return self.get_chat_messages()

        # HOME
        if path == "/":

            return self.serve_static(
                "index.html"
            )

        # FAVICON
        if path == "/favicon.ico":

            self.send_response(
                204
            )

            self.end_headers()

            return

        # STATIC FILE
        relative_path = path.lstrip("/")

        allowed_extensions = {
            ".html",
            ".css",
            ".js",
            ".json",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
            ".ico",
            ".mp3",
            ".wav",
            ".mp4",
            ".webm"
        }

        extension = Path(
            relative_path
        ).suffix.lower()

        if extension in allowed_extensions:

            return self.serve_static(
                relative_path
            )

        return send_json(
            self,
            404,
            {
                "success":
                    False,

                "message":
                    "مسیر پیدا نشد."
            }
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    def do_POST(self):

        path = self.path.split(
            "?",
            1
        )[0]

        if path == "/api/login":

            return self.login()

        if path == "/api/register":

            return self.register()

        if path == "/api/streams/create":

            return self.create_stream()

        if path == "/api/streams/stop":

            return self.stop_stream()

        if path == "/api/streams/viewer":

            return self.viewer_count()

        if path == "/api/chat/send":

            return self.send_chat()

        return send_json(
            self,
            404,
            {
                "success":
                    False,

                "message":
                    "مسیر پیدا نشد."
            }
        )

    # =====================================================
    # LOGIN
    # =====================================================

    def login(self):

        data = read_json(
            self
        )

        username = clean_username(
            data.get(
                "username"
            )
        )

        password = str(
            data.get(
                "password",
                ""
            )
        )

        if (
            not username
            or not password
        ):

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "نام کاربری و رمز عبور را وارد کنید."
                }
            )

        with users_lock:

            user = users.get(
                username
            )

            if (
                not user
                or not verify_password(
                    password,
                    user
                )
            ):

                return send_json(
                    self,
                    401,
                    {
                        "success":
                            False,

                        "message":
                            "نام کاربری یا رمز عبور اشتباه است."
                    }
                )

        return send_json(
            self,
            200,
            {
                "success":
                    True,

                "username":
                    username
            }
        )

    # =====================================================
    # REGISTER
    # =====================================================

    def register(self):

        data = read_json(
            self
        )

        username = clean_username(
            data.get(
                "username"
            )
        )

        password = str(
            data.get(
                "password",
                ""
            )
        )

        if not valid_username(
            username
        ):

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "نام کاربری باید بین 3 تا 30 کاراکتر باشد."
                }
            )

        if not valid_password(
            password
        ):

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "رمز عبور باید حداقل 6 کاراکتر باشد."
                }
            )

        with users_lock:

            if username in users:

                return send_json(
                    self,
                    409,
                    {
                        "success":
                            False,

                        "message":
                            "این نام کاربری قبلاً ثبت شده است."
                    }
                )

            users[username] = {
                **hash_password(
                    password
                ),
                "created_at":
                    int(
                        time.time()
                    )
            }

            save_users(
                users
            )

        return send_json(
            self,
            201,
            {
                "success":
                    True,

                "username":
                    username,

                "message":
                    "ثبت‌نام با موفقیت انجام شد."
            }
        )

    # =====================================================
    # CREATE STREAM
    # =====================================================

    def create_stream(self):

        data = read_json(
            self
        )

        username = clean_username(
            data.get(
                "username"
            )
        )

        title = clean_text(
            data.get(
                "title"
            ),
            100
        )

        if not username:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "نام کاربری ارسال نشده است."
                }
            )

        with users_lock:

            if username not in users:

                return send_json(
                    self,
                    401,
                    {
                        "success":
                            False,

                        "message":
                            "کاربر پیدا نشد."
                    }
                )

        if not title:

            title = (
                "لایو "
                + username
            )

        global next_stream_id

        now = int(
            time.time()
        )

        with streams_lock:

            stream_id = str(
                next_stream_id
            )

            next_stream_id += 1

            stream = {
                "id":
                    stream_id,

                "title":
                    title,

                "username":
                    username,

                "created_at":
                    now,

                "started_at":
                    now,

                "viewer_count":
                    0,

                "viewer_peak":
                    0
            }

            streams[
                stream_id
            ] = stream

        with chat_lock:

            chat_messages[
                stream_id
            ] = []

        return send_json(
            self,
            201,
            {
                "success":
                    True,

                "stream":
                    stream_public_data(
                        stream
                    )
            }
        )

    # =====================================================
    # STOP STREAM
    # =====================================================

    def stop_stream(self):

        data = read_json(
            self
        )

        stream_id = str(
            data.get(
                "stream_id",
                ""
            )
        )

        username = clean_username(
            data.get(
                "username"
            )
        )

        if not stream_id:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "شناسه لایو نامعتبر است."
                }
            )

        with streams_lock:

            stream = streams.get(
                stream_id
            )

            if not stream:

                return send_json(
                    self,
                    404,
                    {
                        "success":
                            False,

                        "message":
                            "لایو پیدا نشد."
                    }
                )

            if (
                username
                and stream["username"]
                != username
            ):

                return send_json(
                    self,
                    403,
                    {
                        "success":
                            False,

                        "message":
                            "شما صاحب این لایو نیستید."
                    }
                )

            ended_at = int(
                time.time()
            )

            started_at = int(
                stream.get(
                    "started_at",
                    stream.get(
                        "created_at",
                        ended_at
                    )
                )
            )

            duration_seconds = max(
                0,
                ended_at - started_at
            )

            history_item = {
                "id":
                    stream["id"],

                "title":
                    stream["title"],

                "username":
                    stream["username"],

                "created_at":
                    stream["created_at"],

                "started_at":
                    started_at,

                "ended_at":
                    ended_at,

                "duration_seconds":
                    duration_seconds,

                "viewer_peak":
                    stream.get(
                        "viewer_peak",
                        stream.get(
                            "viewer_count",
                            0
                        )
                    ),

                "viewer_count":
                    stream.get(
                        "viewer_count",
                        0
                    )
            }

            streams.pop(
                stream_id,
                None
            )

        # ذخیره تاریخچه
        with history_lock:

            stream_history.append(
                history_item
            )

            # جدیدترین لایوها اول باشند
            stream_history.sort(
                key=lambda item:
                    item.get(
                        "ended_at",
                        0
                    ),
                reverse=True
            )

            save_stream_history()

        with chat_lock:

            chat_messages.pop(
                stream_id,
                None
            )

        return send_json(
            self,
            200,
            {
                "success":
                    True,

                "message":
                    "لایو پایان یافت.",

                "history":
                    history_public_data(
                        history_item
                    )
            }
        )

    # =====================================================
    # VIEWER COUNT
    # =====================================================

    def viewer_count(self):

        data = read_json(
            self
        )

        stream_id = str(
            data.get(
                "stream_id",
                ""
            )
        )

        action = str(
            data.get(
                "action",
                ""
            )
        ).lower()

        if action not in {
            "join",
            "leave"
        }:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "عملیات نامعتبر است."
                }
            )

        with streams_lock:

            stream = streams.get(
                stream_id
            )

            if not stream:

                return send_json(
                    self,
                    404,
                    {
                        "success":
                            False,

                        "message":
                            "لایو پیدا نشد."
                    }
                )

            if action == "join":

                stream[
                    "viewer_count"
                ] += 1

                if stream[
                    "viewer_count"
                ] > stream.get(
                    "viewer_peak",
                    0
                ):

                    stream[
                        "viewer_peak"
                    ] = stream[
                        "viewer_count"
                    ]

            else:

                stream[
                    "viewer_count"
                ] = max(
                    0,
                    stream[
                        "viewer_count"
                    ] - 1
                )

            count = stream[
                "viewer_count"
            ]

            peak = stream.get(
                "viewer_peak",
                0
            )

        return send_json(
            self,
            200,
            {
                "success":
                    True,

                "viewer_count":
                    count,

                "viewer_peak":
                    peak
            }
        )

    # =====================================================
    # STREAM HISTORY API
    # =====================================================

    def get_stream_history(self):

        parsed = urllib.parse.urlparse(
            self.path
        )

        params = urllib.parse.parse_qs(
            parsed.query
        )

        username = clean_username(
            params.get(
                "username",
                [""]
            )[0]
        )

        try:

            limit = int(
                params.get(
                    "limit",
                    ["50"]
                )[0]
            )

        except ValueError:

            limit = 50

        limit = max(
            1,
            min(
                limit,
                200
            )
        )

        with history_lock:

            items = list(
                stream_history
            )

        if username:

            items = [
                item
                for item
                in items
                if item.get(
                    "username"
                ) == username
            ]

        items.sort(
            key=lambda item:
                item.get(
                    "ended_at",
                    0
                ),
            reverse=True
        )

        items = items[:limit]

        result = [
            history_public_data(
                item
            )
            for item
            in items
        ]

        return send_json(
            self,
            200,
            {
                "success":
                    True,

                "count":
                    len(result),

                "history":
                    result
            }
        )

    # =====================================================
    # SEND CHAT
    # =====================================================

    def send_chat(self):

        data = read_json(
            self
        )

        stream_id = str(
            data.get(
                "stream_id",
                ""
            )
        )

        username = clean_username(
            data.get(
                "username"
            )
        )

        text = clean_text(
            data.get(
                "text"
            ),
            MAX_MESSAGE_LENGTH
        )

        if not stream_id:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "شناسه لایو نامعتبر است."
                }
            )

        if not username:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "نام کاربری نامعتبر است."
                }
            )

        if not text:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "پیام خالی است."
                }
            )

        with users_lock:

            if username not in users:

                return send_json(
                    self,
                    401,
                    {
                        "success":
                            False,

                        "message":
                            "کاربر پیدا نشد."
                    }
                )

        with streams_lock:

            if stream_id not in streams:

                return send_json(
                    self,
                    404,
                    {
                        "success":
                            False,

                        "message":
                            "لایو پیدا نشد."
                    }
                )

        global next_chat_id

        message = {
            "id":
                str(
                    next_chat_id
                ),

            "username":
                username,

            "text":
                text,

            "created_at":
                int(
                    time.time()
                )
        }

        next_chat_id += 1

        with chat_lock:

            messages = chat_messages.setdefault(
                stream_id,
                []
            )

            messages.append(
                message
            )

            if len(messages) > MAX_CHAT_MESSAGES:

                del messages[
                    :-MAX_CHAT_MESSAGES
                ]

        return send_json(
            self,
            201,
            {
                "success":
                    True,

                "message":
                    message
            }
        )

    # =====================================================
    # GET CHAT MESSAGES
    # =====================================================

    def get_chat_messages(self):

        parsed = urllib.parse.urlparse(
            self.path
        )

        params = urllib.parse.parse_qs(
            parsed.query
        )

        stream_id = params.get(
            "stream_id",
            [""]
        )[0]

        after_id = params.get(
            "after_id",
            [""]
        )[0]

        with streams_lock:

            if stream_id not in streams:

                return send_json(
                    self,
                    404,
                    {
                        "success":
                            False,

                        "message":
                            "لایو پیدا نشد."
                    }
                )

        with chat_lock:

            messages = list(
                chat_messages.get(
                    stream_id,
                    []
                )
            )

        if after_id:

            try:

                after_number = int(
                    after_id
                )

                messages = [
                    message
                    for message
                    in messages
                    if int(
                        message["id"]
                    ) > after_number
                ]

            except ValueError:

                pass

        return send_json(
            self,
            200,
            {
                "success":
                    True,

                "messages":
                    messages
            }
        )

    # =====================================================
    # STATIC FILES
    # =====================================================

    def serve_static(
        self,
        relative_path
    ):

        requested = Path(
            relative_path
        )

        if (
            requested.is_absolute()
            or ".." in requested.parts
        ):

            return send_json(
                self,
                403,
                {
                    "success":
                        False,

                    "message":
                        "دسترسی غیرمجاز."
                }
            )

        file_path = (
            BASE_DIR /
            requested
        ).resolve()

        try:

            file_path.relative_to(
                BASE_DIR
            )

        except ValueError:

            return send_json(
                self,
                403,
                {
                    "success":
                        False,

                    "message":
                        "دسترسی غیرمجاز."
                }
            )

        if not file_path.is_file():

            return send_json(
                self,
                404,
                {
                    "success":
                        False,

                    "message":
                        "فایل پیدا نشد."
                }
            )

        try:

            data = file_path.read_bytes()

        except OSError:

            return send_json(
                self,
                500,
                {
                    "success":
                        False,

                    "message":
                        "خواندن فایل ناموفق بود."
                }
            )

        extension = (
            file_path.suffix.lower()
        )

        content_types = {
            ".html":
                "text/html; charset=utf-8",

            ".css":
                "text/css; charset=utf-8",

            ".js":
                "application/javascript; charset=utf-8",

            ".json":
                "application/json; charset=utf-8",

            ".svg":
                "image/svg+xml",

            ".png":
                "image/png",

            ".jpg":
                "image/jpeg",

            ".jpeg":
                "image/jpeg",

            ".gif":
                "image/gif",

            ".webp":
                "image/webp",

            ".ico":
                "image/x-icon",

            ".mp3":
                "audio/mpeg",

            ".wav":
                "audio/wav",

            ".mp4":
                "video/mp4",

            ".webm":
                "video/webm"
        }

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            content_types.get(
                extension,
                "application/octet-stream"
            )
        )

        self.send_header(
            "Content-Length",
            str(
                len(data)
            )
        )

        self.send_header(
            "Cache-Control",
            "no-cache"
        )

        self.end_headers()

        self.wfile.write(
            data
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=" * 60
    )

    print(
        "LainoLive"
    )

    print(
        "=" * 60
    )

    print(
        f"History file: {HISTORY_FILE}"
    )

    print(
        f"History count: {len(stream_history)}"
    )

    server = ThreadingHTTPServer(
        (
            HOST,
            PORT
        ),
        LainoHandler
    )

    print(
        f"Home:   http://127.0.0.1:{PORT}/"
    )

    print(
        f"Health: http://127.0.0.1:{PORT}/health"
    )

    print(
        f"History: http://127.0.0.1:{PORT}/api/streams/history"
    )

    print(
        "Live: enabled"
    )

    print(
        "Chat: enabled"
    )

    print(
        "History: enabled"
    )

    print(
        "=" * 60
    )

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print(
            "\nLainoLive stopped."
        )

    finally:

        server.server_close()


if __name__ == "__main__":

    main()