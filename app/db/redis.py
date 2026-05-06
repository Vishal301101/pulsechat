import redis.asyncio as aioredis
from app.core.config import settings

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connection = 20,
    decode_response = True # returns string not bytes
) 

async def get_redis() -> aioredis.Redis:
    """Dependancy- Injects a redis client into any route that needs one."""
    return aioredis.Redis(connection_pool=redis_pool)
