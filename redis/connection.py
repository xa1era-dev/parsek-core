import os

import redis.asyncio

# decode_responses=True makes Redis return strings instead of bytes
r = redis.asyncio.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)
