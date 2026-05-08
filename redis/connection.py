import redis.asyncio

# decode_responses=True makes Redis return strings instead of bytes
r = redis.asyncio.Redis(host="localhost", port=6379, decode_responses=True)
