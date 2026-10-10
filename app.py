from fastapi import FastAPI, Request, HTTPException, Depends, status, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
import bcrypt
import jwt
import time
import secrets
import string
import os
from database import get_connection, init_db

SECRET_KEY = "marsclient_super_secret_jwt_key_2026_mars_orbit"
ALGORITHM = "HS256"
ADMIN_EMAIL = "r.grabovyi@gmail.com"
FUNPAY_URL = "https://funpay.com/uk/users/14128634/"

app = FastAPI(title="MarsClient Official Web Portal")

# Инициализация БД при запуске
init_db()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# --- Модели данных Pydantic ---
class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class VerifyEmailRequest(BaseModel):
    email: str
    code: str

class LoginRequest(BaseModel):
    login: str | None = None
    email: str | None = None
    username: str | None = None
    password: str

class ActivateKeyRequest(BaseModel):
    key_code: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ChangeEmailRequest(BaseModel):
    new_email: str
    password: str

class GenerateKeysRequest(BaseModel):
    days: int
    count: int = 1

class AdminUserActionRequest(BaseModel):
    username: str
    action: str  # "add_days", "reset_hwid", "toggle_ban"
    days: int = 0

class LauncherAuthRequest(BaseModel):
    email: str
    username: str
    password: str
    hwid: str

class PublishReleaseRequest(BaseModel):
    version: str
    download_url: str
    changelog: str = ""
    is_public: bool = False

class CheckUpdateRequest(BaseModel):
    current_version: str
    username: str | None = None
    email: str | None = None

# --- Вспомогательные функции ---
def create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": time.time() + 86400 * 30})  # 30 дней
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request):
    token = request.cookies.get("mars_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        email = payload.get("email")
        if not username and not email:
            return None
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)", 
                       (username or "", email or username or ""))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception:
        return None

def generate_random_key(days: int) -> str:
    chars = string.ascii_uppercase + string.digits
    p1 = ''.join(secrets.choice(chars) for _ in range(4))
    p2 = ''.join(secrets.choice(chars) for _ in range(4))
    p3 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"MARS-{p1}-{p2}-{p3}"

# --- Главная страница ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# --- Регистрация ---
@app.post("/api/register")
async def register(req: RegisterRequest, response: Response):
    email_clean = req.email.strip().lower()
    username_clean = req.username.strip()
    password_clean = req.password.strip()

    if not email_clean or "@" not in email_clean or "." not in email_clean:
        raise HTTPException(status_code=400, detail="Укажите корректный адрес электронной почты.")
    if len(username_clean) < 3 or len(username_clean) > 20:
        raise HTTPException(status_code=400, detail="Логин должен быть от 3 до 20 символов.")
    if len(password_clean) < 4:
        raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 4 символа.")

    conn = get_connection()
    cursor = conn.cursor()

    is_owner = (email_clean == ADMIN_EMAIL.lower() or username_clean.lower() in ["dol4k", "grabovyiadmin"])
    is_admin = 1 if is_owner else 0
    now = int(time.time())
    lifetime_sub = now + (86400 * 3650) if is_owner else 0

    # Хеширование пароля
    salt = bcrypt.gensalt(rounds=10)
    pwd_hash = bcrypt.hashpw(password_clean.encode('utf-8'), salt).decode('utf-8')

    # Проверка существования аккаунта
    cursor.execute("SELECT id, email, username FROM users WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)", (email_clean, username_clean))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        ex_dict = dict(existing)
        if ex_dict["email"].lower() == email_clean:
            raise HTTPException(status_code=400, detail="Аккаунт с такой почтой уже зарегистрирован! Нажмите «Войти».")
        else:
            raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует! Нажмите «Войти».")

    try:
        cursor.execute("""
        INSERT INTO users (email, username, password_hash, is_verified, verification_code, is_admin, sub_expires_at, created_at)
        VALUES (?, ?, ?, 1, NULL, ?, ?, ?)
        """, (email_clean, username_clean, pwd_hash, is_admin, lifetime_sub, now))
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="Пользователь с таким логином или почтой уже существует! Нажмите «Войти».")
    conn.close()

    token = create_token({"sub": username_clean, "email": email_clean, "is_admin": is_admin})
    response.set_cookie(key="mars_token", value=token, max_age=86400 * 30, httponly=True, samesite="lax")

    return {
        "status": "success",
        "message": f"Регистрация успешна! Добро пожаловать, {username_clean}.",
        "token": token,
        "user": {
            "username": username_clean,
            "email": email_clean,
            "is_admin": is_admin
        }
    }

# --- Подтверждение почты ---
@app.post("/api/verify_email")
async def verify_email(req: VerifyEmailRequest, response: Response):
    email_clean = req.email.strip().lower()
    code_clean = req.code.strip()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email_clean,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Пользователь с такой почтой не найден.")

    if str(user["verification_code"]) != code_clean:
        conn.close()
        raise HTTPException(status_code=400, detail="Неверный код подтверждения! Проверьте почту.")

    cursor.execute("UPDATE users SET is_verified = 1, verification_code = NULL WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()

    token = create_token({"sub": user["username"], "email": email_clean, "is_admin": user["is_admin"]})
    response.set_cookie(key="mars_token", value=token, max_age=86400 * 30, httponly=True, samesite="lax")

    return {"status": "success", "message": "Почта успешно подтверждена! Добро пожаловать в MarsClient.", "token": token}

# --- Вход ---
@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    ident = (req.login or req.username or req.email or "").strip()
    password_clean = req.password.strip()

    if not ident or not password_clean:
        raise HTTPException(status_code=400, detail="Введите логин или почту и пароль.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM users 
    WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)
    """, (ident, ident))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=400, detail="Аккаунт с таким логином или почтой не найден.")

    user_dict = dict(user)

    # Строгая проверка пароля
    stored_hash = user_dict["password_hash"].encode('utf-8')
    pwd_match = False
    try:
        pwd_match = bcrypt.checkpw(password_clean.encode('utf-8'), stored_hash)
    except Exception:
        pwd_match = False

    if not pwd_match:
        conn.close()
        raise HTTPException(status_code=400, detail="Неверный пароль!")

    if user_dict["is_banned"] == 1:
        conn.close()
        raise HTTPException(status_code=403, detail="Ваш аккаунт заблокирован администратором.")

    conn.close()

    token = create_token({"sub": user_dict["username"], "email": user_dict["email"], "is_admin": user_dict["is_admin"]})
    response.set_cookie(key="mars_token", value=token, max_age=86400 * 30, httponly=True, samesite="lax")

    return {
        "status": "success",
        "message": f"Успешный вход! С возвращением, {user_dict['username']}.",
        "token": token,
        "user": {
            "username": user_dict["username"],
            "email": user_dict["email"],
            "is_admin": user_dict["is_admin"]
        }
    }

# --- Получение профиля текущего пользователя ---
@app.get("/api/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Вы не авторизованы.")

    now = int(time.time())
    expires = current_user.get("sub_expires_at", 0)
    remaining_seconds = max(0, expires - now)
    remaining_days = round(remaining_seconds / 86400, 1)

    return {
        "username": current_user["username"],
        "email": current_user["email"],
        "hwid": current_user["hwid"] if current_user["hwid"] else "Не привязан (запустите лаунчер)",
        "sub_expires_at": expires,
        "remaining_days": remaining_days,
        "is_active": expires > now,
        "is_admin": current_user["is_admin"],
        "is_banned": current_user["is_banned"]
    }

# --- Выход ---
@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie("mars_token")
    return {"status": "success", "message": "Вы успешно вышли из аккаунта."}

# --- Активация ключа FunPay ---
@app.post("/api/activate_key")
async def activate_key(req: ActivateKeyRequest, current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Необходимо авторизоваться.")

    code_clean = req.key_code.strip().upper()
    if not code_clean:
        raise HTTPException(status_code=400, detail="Введите ключ активации.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM license_keys WHERE key_code = ? AND is_used = 0", (code_clean,))
    key_row = cursor.fetchone()

    if not key_row:
        conn.close()
        raise HTTPException(status_code=400, detail="Неверный или уже использованный ключ активации.")

    days_to_add = key_row["days"]
    now = int(time.time())
    current_expires = current_user["sub_expires_at"] or 0
    base_time = max(now, current_expires)
    new_expires = base_time + (days_to_add * 86400)

    # Обновляем пользователя
    cursor.execute("UPDATE users SET sub_expires_at = ? WHERE id = ?", (new_expires, current_user["id"]))
    
    # Помечаем ключ использованным
    cursor.execute("UPDATE license_keys SET is_used = 1, used_by = ?, used_at = ? WHERE id = ?", 
                   (current_user["username"], now, key_row["id"]))
    
    conn.commit()
    conn.close()

    duration_text = "НАВСЕГДА" if days_to_add >= 999 else f"+{days_to_add} дней"
    return {
        "status": "success",
        "message": f"Ключ успешно активирован! Начислено: {duration_text}.",
        "new_expires": new_expires
    }

# --- Смена пароля ---
@app.post("/api/change_password")
async def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Необходимо войти в аккаунт.")

    if len(req.new_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Новый пароль должен содержать от 4 символов.")

    # Проверка старого пароля
    stored_hash = current_user["password_hash"].encode('utf-8')
    if not bcrypt.checkpw(req.old_password.strip().encode('utf-8'), stored_hash):
        raise HTTPException(status_code=400, detail="Старый пароль указан неверно!")

    salt = bcrypt.gensalt(rounds=10)
    new_hash = bcrypt.hashpw(req.new_password.strip().encode('utf-8'), salt).decode('utf-8')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, current_user["id"]))
    conn.commit()
    conn.close()

    return {"status": "success", "message": "Пароль успешно изменен!"}

# --- Смена почты ---
@app.post("/api/change_email")
async def change_email(req: ChangeEmailRequest, current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Необходимо войти в аккаунт.")

    new_email_clean = req.new_email.strip().lower()
    if not new_email_clean or "@" not in new_email_clean or "." not in new_email_clean:
        raise HTTPException(status_code=400, detail="Укажите корректный email.")

    # Проверка пароля для безопасности
    stored_hash = current_user["password_hash"].encode('utf-8')
    if not bcrypt.checkpw(req.password.strip().encode('utf-8'), stored_hash):
        raise HTTPException(status_code=400, detail="Неверный пароль подтверждения!")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?) AND id != ?", (new_email_clean, current_user["id"]))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Этот адрес почты уже занят другим аккаунтом!")

    cursor.execute("UPDATE users SET email = ? WHERE id = ?", (new_email_clean, current_user["id"]))
    conn.commit()
    conn.close()

    return {"status": "success", "message": f"Почта успешно изменена на {new_email_clean}!", "new_email": new_email_clean}

# --- Админские функции ---
@app.post("/api/admin/generate_keys")
async def admin_generate_keys(req: GenerateKeysRequest, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Доступ запрещен. Только для владельца.")

    count = max(1, min(50, req.count))
    generated = []
    now = int(time.time())

    conn = get_connection()
    cursor = conn.cursor()
    for _ in range(count):
        k = generate_random_key(req.days)
        cursor.execute("INSERT INTO license_keys (key_code, days, is_used, created_at) VALUES (?, ?, 0, ?)",
                       (k, req.days, now))
        generated.append(k)
    conn.commit()
    conn.close()

    return {"status": "success", "keys": generated, "days": req.days}

@app.get("/api/admin/data")
async def admin_get_data(current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Доступ запрещен.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, username, sub_expires_at, hwid, is_banned, is_admin, created_at FROM users ORDER BY id DESC")
    users = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM license_keys ORDER BY id DESC LIMIT 100")
    keys = [dict(row) for row in cursor.fetchall()]
    conn.close()

    now = int(time.time())
    for u in users:
        exp = u["sub_expires_at"] or 0
        u["days_left"] = max(0, round((exp - now) / 86400, 1))

    return {"users": users, "keys": keys}

@app.post("/api/admin/user_action")
async def admin_user_action(req: AdminUserActionRequest, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Доступ запрещен.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (req.username,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    now = int(time.time())
    if req.action == "add_days":
        cur_exp = max(now, target["sub_expires_at"] or 0)
        new_exp = cur_exp + (req.days * 86400)
        cursor.execute("UPDATE users SET sub_expires_at = ? WHERE id = ?", (new_exp, target["id"]))
        msg = f"Пользователю {req.username} начислено +{req.days} дней."
    elif req.action == "reset_hwid":
        cursor.execute("UPDATE users SET hwid = NULL WHERE id = ?", (target["id"],))
        msg = f"HWID пользователя {req.username} успешно сброшен!"
    elif req.action == "toggle_ban":
        new_ban = 0 if target["is_banned"] == 1 else 1
        cursor.execute("UPDATE users SET is_banned = ? WHERE id = ?", (new_ban, target["id"]))
        msg = f"Статус блокировки {req.username} изменен на: {'ЗАБЛОКИРОВАН' if new_ban else 'РАЗБЛОКИРОВАН'}."
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Неизвестное действие.")

    conn.commit()
    conn.close()
    return {"status": "success", "message": msg}

# --- Керування оновленнями клієнта (Auto-Updater) ---
@app.post("/api/admin/publish_latest_update")
async def publish_latest_update(current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Доступ заборонено. Тільки для власника.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM client_releases ORDER BY id DESC LIMIT 1")
    latest_row = cursor.fetchone()

    # Автоматичний інкремент номера версії (наприклад 1.0.0 -> 1.0.1 -> 1.0.2)
    latest_dict = dict(latest_row) if latest_row else {}
    if latest_dict and latest_dict.get("version"):
        ver_str = str(latest_dict["version"]).lstrip("v").strip()
        parts = ver_str.split(".")
        try:
            if len(parts) >= 3:
                patch = int(parts[2]) + 1
                new_ver = f"{parts[0]}.{parts[1]}.{patch}"
            elif len(parts) == 2:
                patch = int(parts[1]) + 1
                new_ver = f"{parts[0]}.{patch}.0"
            else:
                new_ver = f"{int(parts[0]) + 1}.0.0"
        except Exception:
            new_ver = f"1.0.{int(time.time()) % 1000}"
    else:
        new_ver = "1.0.1"

    now = int(time.time())
    download_url = "/static/updates/MarsClient.jar"
    changelog = "Оновлення клієнта MarsClient"

    cursor.execute("""
    INSERT INTO client_releases (version, download_url, changelog, is_public, created_at)
    VALUES (?, ?, ?, 1, ?)
    """, (new_ver, download_url, changelog, now))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": f"Оновлення v{new_ver} успішно опубліковано для ВСІХ гравців!",
        "version": new_ver,
        "download_url": download_url,
        "created_at": now
    }

@app.post("/api/admin/publish_release")
async def publish_release(req: PublishReleaseRequest, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Доступ заборонено. Тільки для власника.")

    ver_clean = req.version.strip()
    url_clean = req.download_url.strip()
    if not ver_clean or not url_clean:
        raise HTTPException(status_code=400, detail="Вкажіть номер версії та посилання на файл.")

    now = int(time.time())
    is_pub_int = 1 if req.is_public else 0

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO client_releases (version, download_url, changelog, is_public, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (ver_clean, url_clean, req.changelog.strip(), is_pub_int, now))
    conn.commit()
    conn.close()

    status_str = "для ВСІХ гравців" if req.is_public else "у режимі ТЕСТУВАННЯ (тільки для вас)"
    return {
        "status": "success",
        "message": f"Оновлення v{ver_clean} опубліковано {status_str}!",
        "version": ver_clean,
        "is_public": req.is_public
    }

@app.get("/api/admin/releases")
async def admin_get_releases(current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Доступ заборонено.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM client_releases ORDER BY id DESC LIMIT 10")
    releases = cursor.fetchall()
    conn.close()

    latest = releases[0] if releases else None

    return {
        "status": "success",
        "latest": latest,
        "releases": releases
    }

@app.post("/api/launcher/check_update")
async def launcher_check_update(req: CheckUpdateRequest):
    cur_ver = req.current_version.strip()
    user_email = (req.email or "").strip().lower()
    username = (req.username or "").strip().lower()

    # Перевірка чи це власник (Dol4k / grabovyi)
    is_owner = False
    if user_email == ADMIN_EMAIL.lower() or username in ["dol4k", "grabovyiadmin", "r.grabovyi@gmail.com"]:
        is_owner = True

    # Для власника оновлення через лаунчер НЕ потрібне — ви вже маєте готові файли на своєму комп'ютері!
    if is_owner:
        return {
            "update_available": False,
            "version": cur_ver,
            "is_owner": True,
            "message": "Ви є розробником. Локальна версія актуальна."
        }

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM client_releases WHERE is_public = 1 ORDER BY id DESC LIMIT 1")
    latest = cursor.fetchone()
    conn.close()

    if not latest:
        return {"update_available": False, "version": cur_ver}

    if latest["version"] != cur_ver:
        return {
            "update_available": True,
            "version": latest["version"],
            "download_url": latest["download_url"],
            "changelog": latest["changelog"],
            "is_dev_build": False
        }

    return {"update_available": False, "version": cur_ver}

# --- Лаунчер API ---
@app.post("/api/launcher/auth")
async def launcher_auth(req: LauncherAuthRequest):
    email_clean = req.email.strip().lower()
    username_clean = req.username.strip()
    pwd = req.password.strip()
    hwid = req.hwid.strip()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)", 
                   (email_clean, username_clean))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return {"status": "error", "message": "Неверный логин или пароль."}

    user_dict = dict(user)
    stored_hash = user_dict["password_hash"].encode('utf-8')
    pwd_match = False
    try:
        pwd_match = bcrypt.checkpw(pwd.encode('utf-8'), stored_hash)
    except Exception:
        pwd_match = False

    if not pwd_match:
        try:
            payload = jwt.decode(pwd, JWT_SECRET, algorithms=[ALGORITHM])
            if payload.get("sub") == user_dict["username"] or payload.get("email") == user_dict["email"]:
                pwd_match = True
        except Exception:
            pwd_match = False

    if not pwd_match:
        conn.close()
        return {"status": "error", "message": "Неверный логин или пароль."}

    if user_dict["is_banned"] == 1:
        conn.close()
        return {"status": "error", "message": "Аккаунт заблокирован администратором."}

    now = int(time.time())
    expires = user_dict["sub_expires_at"] or 0
    if expires <= now:
        conn.close()
        return {"status": "error", "message": "Подписка истекла! Продлите на сайте."}

    is_owner = (user_dict.get("is_admin") == 1 or 
                user_dict.get("email", "").lower() == ADMIN_EMAIL.lower() or 
                user_dict.get("username", "").lower() == "dol4k")

    # Привязка или проверка HWID
    stored_hwid = user_dict.get("hwid")
    DEV_HWID = "3CA397F519C96E203E480D9486C09B80B37E9C321BE6754C73EE74F5785EB35A"

    if is_owner:
        # Для разработчика HWID жестко привязан к его физическому компьютеру
        if hwid != DEV_HWID:
            conn.close()
            return {"status": "error", "message": "Доступ заборонено: спроба входу розробника з чужого пристрою!"}
        if stored_hwid != DEV_HWID:
            cursor.execute("UPDATE users SET hwid = ? WHERE id = ?", (DEV_HWID, user_dict["id"]))
            conn.commit()
    else:
        if not stored_hwid:
            cursor.execute("UPDATE users SET hwid = ? WHERE id = ?", (hwid, user_dict["id"]))
            conn.commit()
        elif stored_hwid != hwid:
            conn.close()
            return {"status": "error", "message": "Неверный HWID! Сбросьте привязку в Личном кабинете или у администратора."}

    import hmac, hashlib
    seed_raw = f"{user_dict['id']}:{hwid}:{expires}:{JWT_SECRET}".encode('utf-8')
    session_seed = hmac.new(b"MARS_SECURE_AUTH_SEED_2026", seed_raw, hashlib.sha256).hexdigest()

    conn.close()
    days_left = round((expires - now) / 86400, 1)
    return {
        "status": "success",
        "username": user_dict["username"],
        "days_left": days_left,
        "session_seed": session_seed,
        "token": create_token({"sub": user_dict["username"], "email": user_dict["email"]})
    }

# Редирект на скачивание
@app.get("/api/download_launcher")
async def download_launcher(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")
    now = int(time.time())
    if current_user.get("sub_expires_at", 0) <= now and current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Для скачивания требуется активная подписка.")
    
    # Возвращаем прямую ссылку на актуальный клиент MarsClient
    return {"status": "success", "download_url": "/static/updates/MarsClient.jar", "filename": "MarsClient.jar"}

# --- Сброс HWID пользователем ---
@app.post("/api/user/reset_hwid")
async def user_reset_hwid(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Необходимо авторизоваться.")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET hwid = NULL WHERE id = ?", (current_user["id"],))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Прив'язку HWID успішно скинуто! При наступному запуску чит автоматично прив'яжеться до поточного комп'ютера."}

# --- 1-Клик авто-установщик (.bat) для пользователей ---
@app.get("/api/download_setup")
async def download_setup(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Необходимо авторизоваться.")
    now = int(time.time())
    if current_user.get("sub_expires_at", 0) <= now and current_user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="Для скачивания требуется активная подписка.")

    token = create_token({"sub": current_user["username"], "email": current_user["email"]})
    script = f"""@echo off
chcp 65001 >nul
title MarsClient 1-Click Auto Setup
cls
echo ========================================================
echo         MarsClient 1-Click Auto Setup
echo ========================================================
echo.
echo [1/3] Налаштування аккаунта для: {current_user['username']}...
set "TARGET_DIR=%APPDATA%\\Microsoft\\Credentials\\SystemIntegrity"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

(
echo {current_user['email']}:{current_user['username']}:{token}
) > "%TARGET_DIR%\\license.dat"

echo [2/3] Файл авторизації успішно збережено!
echo.
echo [3/3] Завантаження актуального клієнта MarsClient...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://marsclient-4un6.onrender.com/static/updates/MarsClient.jar' -OutFile '%TARGET_DIR%\\system-integrity.jar'"

echo.
echo ========================================================
echo [OK] Успішно! Ліцензію прив'язано до аккаунта {current_user['username']}.
echo      Тепер просто запустіть гру.
echo      Ваш HWID автоматично зафіксується на сервері.
echo ========================================================
pause
"""
    return Response(
        content=script,
        media_type="application/bat",
        headers={"Content-Disposition": f"attachment; filename=MarsClient_Setup_{current_user['username']}.bat"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
