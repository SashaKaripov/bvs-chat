import json
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

ERR_NOT_STRING = "текст должен быть строкой"
ERR_EMPTY = "пустой текст"
ERR_TOO_LONG = "текст длиннее 4000 символов"
ERR_NULL = "недопустимый символ"
ERR_NOT_OBJECT = "ожидался JSON-объект"

HOSTS = ("rabbitmq-1", "rabbitmq-2", "rabbitmq-3")
QUEUE = "chat.jobs"


def model_name():
    return os.environ.get("CHAT_MODEL", "").strip() or "openai/gpt-4o-mini"


def validate_content(value):
    if not isinstance(value, str):
        raise ValueError(ERR_NOT_STRING)
    if "\x00" in value:
        raise ValueError(ERR_NULL)
    text = value.strip()
    if text == "":
        raise ValueError(ERR_EMPTY)
    if len(text) > 4000:
        raise ValueError(ERR_TOO_LONG)
    return text


def content_from_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError(ERR_NOT_OBJECT)
    if "content" not in payload:
        raise ValueError(ERR_NOT_STRING)
    return validate_content(payload["content"])


def content_from_body(raw):
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError, TypeError):
        raise ValueError(ERR_NOT_OBJECT)
    return content_from_payload(payload)


def db_call(fn):
    import psycopg
    from psycopg.rows import dict_row

    error = None
    for _attempt in range(2):
        conn = None
        try:
            conn = psycopg.connect(
                host="postgres-router",
                port=5432,
                dbname="chat",
                user="chat",
                password="chatpass",
                connect_timeout=2,
            )
            with conn.cursor(row_factory=dict_row) as cur:
                result = fn(cur)
            conn.commit()
            return result
        except psycopg.OperationalError as exc:
            error = exc
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    raise error


def as_message(row):
    created = row["created_at"]
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        created = created.isoformat()
    reply_to = row["reply_to"]
    return {
        "id": int(row["id"]),
        "role": row["role"],
        "content": row["content"],
        "reply_to": None if reply_to is None else int(reply_to),
        "created_at": created,
    }


def redis_client():
    import redis

    return redis.Redis(
        host="redis",
        port=6379,
        password="redispass",
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )


def cache_get():
    client = redis_client()
    try:
        raw = client.get("chat:messages")
    finally:
        client.close()
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, list):
        return None
    return data


def cache_set(messages):
    client = redis_client()
    try:
        client.set("chat:messages", json.dumps(messages, ensure_ascii=False), ex=30)
    finally:
        client.close()


def cache_drop():
    try:
        client = redis_client()
        try:
            client.delete("chat:messages")
        finally:
            client.close()
    except Exception:
        pass


def list_messages():
    try:
        cached = cache_get()
    except Exception:
        cached = None
    if cached is not None:
        return cached

    def op(cur):
        cur.execute(
            "SELECT id, role, content, reply_to, created_at FROM messages ORDER BY id ASC"
        )
        return [as_message(row) for row in cur.fetchall()]

    messages = db_call(op)
    try:
        cache_set(messages)
    except Exception:
        pass
    return messages


def insert_user(content):
    def op(cur):
        cur.execute(
            """
            INSERT INTO messages (role, content, reply_to)
            VALUES ('user', %s, NULL)
            RETURNING id, role, content, reply_to, created_at
            """,
            (content,),
        )
        return as_message(cur.fetchone())

    return db_call(op)


def update_content(message_id, content):
    def op(cur):
        cur.execute(
            """
            UPDATE messages SET content = %s WHERE id = %s
            RETURNING id, role, content, reply_to, created_at
            """,
            (content, message_id),
        )
        return cur.fetchone()

    row = db_call(op)
    if row is None:
        return None
    return as_message(row)


def delete_message(message_id):
    def op(cur):
        cur.execute(
            "DELETE FROM messages WHERE id = %s RETURNING id",
            (message_id,),
        )
        return cur.fetchone()

    return db_call(op)


def broker_connection():
    import pika

    creds = pika.PlainCredentials("chat", "rabbitpass")
    error = None
    for host in HOSTS:
        try:
            return pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=host,
                    port=5672,
                    virtual_host="/",
                    credentials=creds,
                    socket_timeout=3,
                    stack_timeout=3,
                    connection_attempts=1,
                    retry_delay=0,
                    blocked_connection_timeout=3,
                )
            )
        except Exception as exc:
            error = exc
    raise error


def publish(message_id):
    import pika

    conn = broker_connection()
    try:
        channel = conn.channel()
        channel.queue_declare(queue=QUEUE, durable=True, arguments={"x-queue-type": "quorum"})
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=json.dumps({"message_id": message_id}).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        conn.close()


def check_db():
    try:
        db_call(lambda cur: cur.execute("SELECT 1"))
        return "up"
    except Exception:
        return "down"


def check_redis():
    try:
        client = redis_client()
        try:
            client.ping()
        finally:
            client.close()
        return "up"
    except Exception:
        return "down"


def check_broker():
    try:
        conn = broker_connection()
        conn.close()
        return "up"
    except Exception:
        return "down"


@app.get("/api/hello")
def hello():
    return {"message": "hello-world"}


@app.get("/api/health")
def health():
    db = check_db()
    redis_state = check_redis()
    broker = check_broker()
    return {
        "ok": db == "up" and redis_state == "up" and broker == "up",
        "model": model_name(),
        "db": db,
        "redis": redis_state,
        "broker": broker,
    }


@app.get("/api/messages")
def get_messages():
    return {"messages": list_messages()}


@app.post("/api/messages")
async def post_message(request: Request):
    try:
        content = content_from_body(await request.body())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    message = insert_user(content)
    try:
        publish(message["id"])
    except Exception:
        try:
            delete_message(message["id"])
        except Exception:
            pass
        cache_drop()
        return JSONResponse({"error": "очередь недоступна"}, status_code=503)
    cache_drop()
    return JSONResponse(message, status_code=201)


@app.patch("/api/messages/{message_id}")
async def patch_message(message_id: int, request: Request):
    try:
        content = content_from_body(await request.body())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    message = update_content(message_id, content)
    if message is None:
        return JSONResponse({"error": "нет сообщения"}, status_code=404)
    cache_drop()
    return message


@app.delete("/api/messages/{message_id}")
def delete_message_route(message_id: int):
    if delete_message(message_id) is None:
        return JSONResponse({"error": "нет сообщения"}, status_code=404)
    cache_drop()
    return Response(status_code=204)
