import json
import logging
import os
import time
import urllib.error
import urllib.request

log = logging.getLogger("worker")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYSTEM_PROMPT = "Ты краткий помощник в учебном чате. Отвечай на языке человека."
FALLBACK = "Модель сейчас не ответила. Попробуй ещё раз."
HOSTS = ("rabbitmq-1", "rabbitmq-2", "rabbitmq-3")
QUEUE = "chat.jobs"


def request_reply(history, api_key, model):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps({"model": model, "messages": messages}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/bvs-chat",
            "X-Title": "bvs-chat",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        code = exc.code
        try:
            exc.close()
        except Exception:
            pass
        raise RuntimeError("openrouter code=%s" % code)
    except Exception:
        raise RuntimeError("openrouter code=unreachable")
    return reply_text(raw)


def reply_text(raw):
    try:
        payload = json.loads(raw.decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
    except (UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        raise RuntimeError("openrouter code=bad-response")
    if not isinstance(content, str):
        raise RuntimeError("openrouter code=empty")
    text = content.replace("\x00", "").strip()
    if text == "":
        raise RuntimeError("openrouter code=empty")
    return text[:4000]


def reply_for_history(history, api_key, model):
    try:
        return request_reply(history, api_key, model)
    except Exception as exc:
        text = str(exc)
        if text.startswith("openrouter code=") and "\n" not in text and len(text) <= 40:
            log.warning("%s", text)
        else:
            log.warning("openrouter error code=error")
        return FALLBACK


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


def cache_drop():
    try:
        client = redis_client()
        try:
            client.delete("chat:messages")
        finally:
            client.close()
    except Exception:
        pass


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


def load_history(message_id):
    def op(cur):
        cur.execute("SELECT id FROM messages WHERE id = %s", (message_id,))
        if cur.fetchone() is None:
            return None
        cur.execute("SELECT id FROM messages WHERE reply_to = %s", (message_id,))
        if cur.fetchone() is not None:
            return "done"
        cur.execute(
            "SELECT id, role, content FROM messages WHERE id <= %s ORDER BY id DESC LIMIT 20",
            (message_id,),
        )
        rows = cur.fetchall()
        if not any(row["id"] == message_id for row in rows):
            return None
        rows.reverse()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    return db_call(op)


def insert_reply(message_id, content):
    def op(cur):
        cur.execute(
            """
            INSERT INTO messages (role, content, reply_to)
            VALUES ('assistant', %s, %s)
            ON CONFLICT (reply_to) DO NOTHING
            """,
            (content, message_id),
        )

    db_call(op)


def handle(message_id, api_key, model):
    history = load_history(message_id)
    if not history or history == "done":
        return
    insert_reply(message_id, reply_for_history(history, api_key, model))
    cache_drop()


def message_id_of(body):
    data = json.loads(body)
    message_id = data["message_id"]
    if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id < 1:
        raise ValueError("bad job")
    return message_id


def on_message(channel, method, body, api_key, model):
    try:
        message_id = message_id_of(body)
    except Exception:
        channel.basic_ack(method.delivery_tag)
        return
    try:
        handle(message_id, api_key, model)
    except Exception:
        channel.basic_nack(method.delivery_tag, requeue=True)
        return
    channel.basic_ack(method.delivery_tag)


def connect_broker():
    import pika

    creds = pika.PlainCredentials("chat", "rabbitpass")
    while True:
        for host in HOSTS:
            try:
                return pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=host,
                        port=5672,
                        virtual_host="/",
                        credentials=creds,
                        socket_timeout=5,
                        stack_timeout=5,
                        connection_attempts=1,
                        retry_delay=0,
                        blocked_connection_timeout=5,
                        heartbeat=0,
                    )
                )
            except Exception:
                pass
        time.sleep(2)


def serve(api_key, model):
    while True:
        conn = connect_broker()
        try:
            channel = conn.channel()
            channel.queue_declare(queue=QUEUE, durable=True, arguments={"x-queue-type": "quorum"})
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=QUEUE,
                on_message_callback=lambda ch, method, props, body: on_message(
                    ch, method, body, api_key, model
                ),
            )
            channel.start_consuming()
        except Exception:
            time.sleep(1)
        finally:
            try:
                conn.close()
            except Exception:
                pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("pika").setLevel(logging.ERROR)
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("CHAT_MODEL", "").strip() or "openai/gpt-4o-mini"
    serve(api_key, model)


if __name__ == "__main__":
    main()
