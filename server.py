import hashlib
import hmac
import json
import mimetypes
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))

BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"

DEFAULT_USERNAME = os.getenv("LAINO_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("LAINO_PASSWORD", "123456")

PBKDF2_ITERATIONS = 200_000


# =========================================================
# PASSWORD
# =========================================================

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    password_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password_bytes,
        salt_bytes,
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

    iterations = int(
        password_data.get(
            "iterations",
            PBKDF2_ITERATIONS
        )
    )

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


# =========================================================
# USERS
# =========================================================

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

        return json.loads(
            raw.decode("utf-8")
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError
    ):
        return {}


# =========================================================
# STATIC FILES
# =========================================================

def get_content_type(path):
    content_type, _ = mimetypes.guess_type(
        str(path)
    )

    if not content_type:
        content_type = (
            "application/octet-stream"
        )

    return content_type


def serve_static_file(handler, relative_path):
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
        file_path.relative_to(BASE_DIR)
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

    content_type = get_content_type(file_path)

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

    def log_message(self, format_string, *args):
        print(
            f"{self.address_string()} - "
            f"{format_string % args}"
        )

    # -----------------------------------------------------
    # OPTIONS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/health":
            return send_json(
                self,
                200,
                {
                    "status": "ok",
                    "service": "LainoLive",
                    "login_method": "username_password",
                    "registration": True
                }
            )

        if path == "/api/status":
            return send_json(
                self,
                200,
                {
                    "service": "LainoLive API",
                    "status": "online",
                    "login_method": "username_password",
                    "registration": True,
                    "sms": False,
                    "otp": False
                }
            )

        if path == "/":
            return serve_static_file(
                self,
                "index.html"
            )

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

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

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/login":
            return self.login()

        if path == "/api/register":
            return self.register()

        return send_json(
            self,
            404,
            {
                "success": False,
                "message": "مسیر پیدا نشد."
            }
        )

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    def login(self):
        data = read_json(self)

        username = str(
            data.get("username", "")
        ).strip()

        password = str(
            data.get("password", "")
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

        if not user:
            return send_json(
                self,
                401,
                {
                    "success": False,
                    "message": (
                        "نام کاربری یا رمز عبور اشتباه است."
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
                        "نام کاربری یا رمز عبور اشتباه است."
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

    # -----------------------------------------------------
    # REGISTER
    # -----------------------------------------------------

    def register(self):
        data = read_json(self)

        username = str(
            data.get("username", "")
        ).strip()

        password = str(
            data.get("password", "")
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
                        "رمز عبور بیش از حد طولانی است."
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
                        "تکرار رمز عبور یکسان نیست."
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
                        "این نام کاربری قبلاً ثبت شده است."
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
                        "ذخیره حساب کاربری ناموفق بود."
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
