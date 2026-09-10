import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))

BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"

PBKDF2_ITERATIONS = 200_000

DEFAULT_USERNAME = os.getenv(
    "LAINO_USERNAME",
    "admin"
)

DEFAULT_PASSWORD = os.getenv(
    "LAINO_PASSWORD",
    "123456"
)

# =========================================================
# USERS
# =========================================================

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS
    ).hex()

    return {
        "salt": salt,
        "hash": password_hash,
        "iterations": PBKDF2_ITERATIONS
    }


def verify_password(password, password_data):
    if not isinstance(password_data, dict):
        return False

    salt = str(password_data.get("salt", ""))
    saved_hash = str(password_data.get("hash", ""))

    if not salt or not saved_hash:
        return False

    try:
        iterations = int(
            password_data.get(
                "iterations",
                PBKDF2_ITERATIONS
            )
        )
    except (TypeError, ValueError):
        return False

    entered_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    ).hex()

    return hmac.compare_digest(
        entered_hash,
        saved_hash
    )


def load_users():
    if not USERS_FILE.exists():
        return {}

    try:
        data = json.loads(
            USERS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except (
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError
    ):
        pass

    return {}


def save_users(users):
    temp_file = USERS_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(
            users,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    temp_file.replace(USERS_FILE)


def ensure_default_user():
    users = load_users()

    if DEFAULT_USERNAME not in users:
        users[DEFAULT_USERNAME] = {
            "username": DEFAULT_USERNAME,
            "password": hash_password(
                DEFAULT_PASSWORD
            )
        }

        save_users(users)


# =========================================================
# LIVE STREAMS
# =========================================================

streams = {}
streams_lock = threading.Lock()

next_stream_id = 1


def create_stream(username, title, category):
    global next_stream_id

    with streams_lock:
        stream_id = str(next_stream_id)
        next_stream_id += 1

        stream = {
            "id": stream_id,
            "title": title,
            "category": category,
            "username": username,
            "viewers": 0,
            "likes": 0,
            "created_at": time.time(),
            "active": True
        }

        streams[stream_id] = stream

        return stream.copy()


def get_streams():
    with streams_lock:
        return [
            stream.copy()
            for stream in streams.values()
            if stream.get("active") is True
        ]


def get_stream(stream_id):
    with streams_lock:
        stream = streams.get(str(stream_id))

        if stream is None:
            return None

        return stream.copy()


def update_stream_viewers(stream_id, change):
    with streams_lock:
        stream = streams.get(str(stream_id))

        if stream is None:
            return None

        current = int(
            stream.get("viewers", 0)
        )

        stream["viewers"] = max(
            0,
            current + change
        )

        return stream.copy()


def stop_stream(stream_id, username):
    with streams_lock:
        stream = streams.get(str(stream_id))

        if stream is None:
            return False

        if stream.get("username") != username:
            return False

        stream["active"] = False

        return True


# =========================================================
# CHAT
# =========================================================

chat_messages = {}
chat_lock = threading.Lock()

CHAT_MAX_MESSAGES = 200
CHAT_MESSAGE_MAX_LENGTH = 500


def add_chat_message(
    stream_id,
    username,
    text
):
    stream_id = str(stream_id)

    username = str(
        username or ""
    ).strip()

    text = str(
        text or ""
    ).strip()

    if not username or not text:
        return None

    if len(text) > CHAT_MESSAGE_MAX_LENGTH:
        return None

    with chat_lock:
        messages = chat_messages.setdefault(
            stream_id,
            []
        )

        message = {
            "id": (
                str(int(time.time() * 1000))
                + "-"
                + secrets.token_hex(4)
            ),
            "username": username,
            "text": text,
            "created_at": time.time()
        }

        messages.append(message)

        if len(messages) > CHAT_MAX_MESSAGES:
            del messages[
                :len(messages) - CHAT_MAX_MESSAGES
            ]

        return message.copy()


def get_chat_messages(
    stream_id,
    after_id=None
):
    stream_id = str(stream_id)

    with chat_lock:
        messages = list(
            chat_messages.get(
                stream_id,
                []
            )
        )

    if after_id:
        after_id = str(after_id)

        found_index = -1

        for index, message in enumerate(messages):
            if str(message.get("id")) == after_id:
                found_index = index
                break

        if found_index >= 0:
            messages = messages[
                found_index + 1:
            ]

    return messages


# =========================================================
# JSON
# =========================================================

def send_json(handler, status_code, data):
    body = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
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

    handler.end_headers()

    handler.wfile.write(body)


def read_json(handler):
    try:
        content_length = int(
            handler.headers.get(
                "Content-Length",
                "0"
            )
        )
    except ValueError:
        return {}

    if content_length <= 0:
        return {}

    try:
        raw = handler.rfile.read(
            content_length
        )

        data = json.loads(
            raw.decode("utf-8")
        )

        if isinstance(data, dict):
            return data

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        OSError
    ):
        pass

    return {}


# =========================================================
# STATIC FILES
# =========================================================

def get_content_type(path):
    content_type, _ = mimetypes.guess_type(
        str(path)
    )

    if not content_type:
        return "application/octet-stream"

    return content_type


def serve_static_file(
    handler,
    relative_path
):
    requested = Path(relative_path)

    if (
        ".." in requested.parts
        or requested.is_absolute()
    ):
        return send_json(
            handler,
            403,
            {
                "success": False,
                "message": "دسترسی غیرمجاز."
            }
        )

    file_path = (
        BASE_DIR / requested
    ).resolve()

    try:
        file_path.relative_to(
            BASE_DIR
        )
    except ValueError:
        return send_json(
            handler,
            403,
            {
                "success": False,
                "message": "دسترسی غیرمجاز."
            }
        )

    if not file_path.is_file():
        return send_json(
            handler,
            404,
            {
                "success": False,
                "message": "فایل پیدا نشد."
            }
        )

    try:
        data = file_path.read_bytes()
    except OSError:
        return send_json(
            handler,
            500,
            {
                "success": False,
                "message": "خواندن فایل ناموفق بود."
            }
        )

    content_type = get_content_type(
        file_path
    )

    extension = file_path.suffix.lower()

    if extension == ".html":
        content_type = "text/html; charset=utf-8"
    elif extension == ".css":
        content_type = "text/css; charset=utf-8"
    elif extension == ".js":
        content_type = (
            "application/javascript; charset=utf-8"
        )
    elif extension == ".json":
        content_type = (
            "application/json; charset=utf-8"
        )

    handler.send_response(200)

    handler.send_header(
        "Content-Type",
        content_type
    )

    handler.send_header(
        "Content-Length",
        str(len(data))
    )

    handler.send_header(
        "Cache-Control",
        "no-cache"
    )

    handler.end_headers()

    handler.wfile.write(data)


# =========================================================
# HTTP HANDLER
# =========================================================

class LainoHandler(BaseHTTPRequestHandler):

    def log_message(
        self,
        format_string,
        *args
    ):
        print(
            f"{self.address_string()} - "
            f"{format_string % args}"
        )

    # =====================================================
    # OPTIONS
    # =====================================================

    def do_OPTIONS(self):
        self.send_response(204)

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

    # =====================================================
    # GET
    # =====================================================

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ---------------------------------------------
        # HEALTH
        # ---------------------------------------------

        if path == "/health":
            return send_json(
                self,
                200,
                {
                    "status": "ok",
                    "service": "LainoLive",
                    "login_method": (
                        "username_password"
                    ),
                    "registration": True,
                    "live": True,
                    "chat": True
                }
            )

        # ---------------------------------------------
        # STATUS
        # ---------------------------------------------

        if path == "/api/status":
            return send_json(
                self,
                200,
                {
                    "service": "LainoLive API",
                    "status": "online",
                    "login_method": (
                        "username_password"
                    ),
                    "registration": True,
                    "live": True,
                    "chat": True,
                    "sms": False,
                    "otp": False
                }
            )

        # ---------------------------------------------
        # STREAM LIST
        # ---------------------------------------------

        if path == "/api/streams":
            return send_json(
                self,
                200,
                {
                    "success": True,
                    "streams": get_streams()
                }
            )

        # ---------------------------------------------
        # CHAT MESSAGES
        # ---------------------------------------------

        if path == "/api/chat/messages":

            query = parse_qs(
                parsed.query
            )

            stream_id = (
                query.get(
                    "stream_id",
                    [""]
                )[0]
            )

            after_id = (
                query.get(
                    "after_id",
                    [""]
                )[0]
            )

            if not stream_id:
                return send_json(
                    self,
                    400,
                    {
                        "success": False,
                        "message": (
                            "شناسه لایو "
                            "مشخص نشده است."
                        )
                    }
                )

            stream = get_stream(
                stream_id
            )

            if (
                stream is None
                or not stream.get("active")
            ):
                return send_json(
                    self,
                    404,
                    {
                        "success": False,
                        "message": (
                            "لایو پیدا نشد "
                            "یا دیگر فعال نیست."
                        )
                    }
                )

            messages = get_chat_messages(
                stream_id,
                after_id
            )

            return send_json(
                self,
                200,
                {
                    "success": True,
                    "messages": messages
                }
            )

        # ---------------------------------------------
        # HOME
        # ---------------------------------------------

        if path == "/":
            return serve_static_file(
                self,
                "index.html"
            )

        # ---------------------------------------------
        # FAVICON
        # ---------------------------------------------

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # ---------------------------------------------
        # STATIC
        # ---------------------------------------------

        relative_path = path.lstrip("/")

        allowed_extensions = {
            ".html",
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
            ".ico",
            ".json",
            ".mp3",
            ".wav",
            ".mp4",
            ".webm"
        }

        extension = Path(
            relative_path
        ).suffix.lower()

        if extension in allowed_extensions:
            return serve_static_file(
                self,
                relative_path
            )

        return send_json(
            self,
            404,
            {
                "success": False,
                "message": "مسیر پیدا نشد."
            }
        )

    # =====================================================
    # POST
    # =====================================================

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
            return self.create_stream_api()

        if path == "/api/streams/stop":
            return self.stop_stream_api()

        if path == "/api/streams/viewer":
            return self.viewer_stream_api()

        if path == "/api/chat/send":
            return self.chat_send()

        return send_json(
            self,
            404,
            {
                "success": False,
                "message": "مسیر پیدا نشد."
            }
        )

    # =====================================================
    # LOGIN
    # =====================================================

    def login(self):
        data = read_json(self)

        username = str(
            data.get(
                "username",
                ""
            )
        ).strip()

        password = str(
            data.get(
                "password",
                ""
            )
        )

        if not username:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "نام کاربری را وارد کنید."
                    )
                }
            )

        if not password:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "رمز عبور را وارد کنید."
                    )
                }
            )

        users = load_users()

        user = users.get(username)

        if not isinstance(user, dict):
            return send_json(
                self,
                401,
                {
                    "success": False,
                    "message": (
                        "نام کاربری یا رمز عبور "
                        "اشتباه است."
                    )
                }
            )

        if not verify_password(
            password,
            user.get("password")
        ):
            return send_json(
                self,
                401,
                {
                    "success": False,
                    "message": (
                        "نام کاربری یا رمز عبور "
                        "اشتباه است."
                    )
                }
            )

        return send_json(
            self,
            200,
            {
                "success": True,
                "message": (
                    "ورود با موفقیت انجام شد."
                ),
                "username": username
            }
        )

    # =====================================================
    # REGISTER
    # =====================================================

    def register(self):
        data = read_json(self)

        username = str(
            data.get(
                "username",
                ""
            )
        ).strip()

        password = str(
            data.get(
                "password",
                ""
            )
        )

        confirm_password = str(
            data.get(
                "confirm_password",
                ""
            )
        )

        if not username:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "نام کاربری را وارد کنید."
                    )
                }
            )

        if len(username) < 3:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "نام کاربری باید حداقل "
                        "3 کاراکتر باشد."
                    )
                }
            )

        if len(username) > 30:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "نام کاربری نباید بیشتر "
                        "از 30 کاراکتر باشد."
                    )
                }
            )

        if not username.replace(
            "_",
            ""
        ).isalnum():
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "نام کاربری فقط می‌تواند "
                        "شامل حروف، عدد و _ باشد."
                    )
                }
            )

        if not password:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "رمز عبور را وارد کنید."
                    )
                }
            )

        if len(password) < 6:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "رمز عبور باید حداقل "
                        "6 کاراکتر باشد."
                    )
                }
            )

        if len(password) > 200:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "رمز عبور بیش از حد "
                        "طولانی است."
                    )
                }
            )

        if password != confirm_password:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "تکرار رمز عبور "
                        "یکسان نیست."
                    )
                }
            )

        users = load_users()

        if username in users:
            return send_json(
                self,
                409,
                {
                    "success": False,
                    "message": (
                        "این نام کاربری قبلاً "
                        "ثبت شده است."
                    )
                }
            )

        users[username] = {
            "username": username,
            "password": hash_password(
                password
            )
        }

        try:
            save_users(users)
        except OSError:
            return send_json(
                self,
                500,
                {
                    "success": False,
                    "message": (
                        "ذخیره حساب کاربری "
                        "ناموفق بود."
                    )
                }
            )

        return send_json(
            self,
            201,
            {
                "success": True,
                "message": (
                    "ثبت‌نام با موفقیت انجام شد."
                ),
                "username": username
            }
        )

    # =====================================================
    # CREATE STREAM
    # =====================================================

    def create_stream_api(self):
        data = read_json(self)

        username = str(
            data.get(
                "username",
                ""
            )
        ).strip()

        title = str(
            data.get(
                "title",
                ""
            )
        ).strip()

        category = str(
            data.get(
                "category",
                "عمومی"
            )
        ).strip()

        if not username:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "کاربر مشخص نشده است."
                    )
                }
            )

        if not title:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "عنوان لایو را وارد کنید."
                    )
                }
            )

        if len(title) > 100:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "عنوان لایو بیش از حد "
                        "طولانی است."
                    )
                }
            )

        stream = create_stream(
            username,
            title,
            category
        )

        return send_json(
            self,
            201,
            {
                "success": True,
                "stream": stream
            }
        )

    # =====================================================
    # STOP STREAM
    # =====================================================

    def stop_stream_api(self):
        data = read_json(self)

        stream_id = str(
            data.get(
                "stream_id",
                ""
            )
        ).strip()

        username = str(
            data.get(
                "username",
                ""
            )
        ).strip()

        if not stream_id:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "شناسه لایو مشخص نشده است."
                    )
                }
            )

        if not username:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "کاربر مشخص نشده است."
                    )
                }
            )

        if not stop_stream(
            stream_id,
            username
        ):
            return send_json(
                self,
                403,
                {
                    "success": False,
                    "message": (
                        "توقف این لایو مجاز نیست."
                    )
                }
            )

        return send_json(
            self,
            200,
            {
                "success": True,
                "message": (
                    "لایو متوقف شد."
                )
            }
        )

    # =====================================================
    # VIEWER
    # =====================================================

    def viewer_stream_api(self):
        data = read_json(self)

        stream_id = str(
            data.get(
                "stream_id",
                ""
            )
        ).strip()

        action = str(
            data.get(
                "action",
                "join"
            )
        ).strip()

        if not stream_id:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "شناسه لایو مشخص نشده است."
                    )
                }
            )

        if action == "leave":
            change = -1
        else:
            change = 1

        stream = update_stream_viewers(
            stream_id,
            change
        )

        if stream is None:
            return send_json(
                self,
                404,
                {
                    "success": False,
                    "message": (
                        "لایو پیدا نشد."
                    )
                }
            )

        return send_json(
            self,
            200,
            {
                "success": True,
                "stream": stream
            }
        )

    # =====================================================
    # SEND CHAT
    # =====================================================

    def chat_send(self):
        data = read_json(self)

        stream_id = str(
            data.get(
                "stream_id",
                ""
            )
        ).strip()

        username = str(
            data.get(
                "username",
                ""
            )
        ).strip()

        text = str(
            data.get(
                "text",
                ""
            )
        ).strip()

        if not stream_id:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "شناسه لایو مشخص نشده است."
                    )
                }
            )

        stream = get_stream(
            stream_id
        )

        if (
            stream is None
            or not stream.get("active")
        ):
            return send_json(
                self,
                404,
                {
                    "success": False,
                    "message": (
                        "این لایو فعال نیست."
                    )
                }
            )

        if not username:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "نام کاربری مشخص نشده است."
                    )
                }
            )

        if not text:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "پیام خالی است."
                    )
                }
            )

        if len(text) > CHAT_MESSAGE_MAX_LENGTH:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": (
                        "پیام بیش از حد طولانی است."
                    )
                }
            )

        message = add_chat_message(
            stream_id,
            username,
            text
        )

        if message is None:
            return send_json(
                self,
                500,
                {
                    "success": False,
                    "message": (
                        "ثبت پیام ناموفق بود."
                    )
                }
            )

        return send_json(
            self,
            201,
            {
                "success": True,
                "message": message
            }
        )


# =========================================================
# MAIN
# =========================================================

def main():
    ensure_default_user()

    server = ThreadingHTTPServer(
        (HOST, PORT),
        LainoHandler
    )

    print("=" * 60)
    print("LainoLive")
    print("=" * 60)

    print(
        f"Home:   http://127.0.0.1:{PORT}/"
    )

    print(
        f"Login:  http://127.0.0.1:{PORT}/login.html"
    )

    print(
        f"Health: http://127.0.0.1:{PORT}/health"
    )

    print(
        f"Status: http://127.0.0.1:{PORT}/api/status"
    )

    print(
        "Login: username + password"
    )

    print(
        "Registration: enabled"
    )

    print(
        "Live: enabled"
    )

    print(
        "Chat: enabled"
    )

    print(
        "SMS: False"
    )

    print(
        "OTP: False"
    )

    print("=" * 60)

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print()
        print("LainoLive stopped.")

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
