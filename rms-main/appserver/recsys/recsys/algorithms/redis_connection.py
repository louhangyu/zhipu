from django.conf import settings
import random
import redis



"""
reddis的相关函数进行封装

"""

keepalive_redis_conn = None


class RedisConnection:
    def __init__(self, hosts_config=settings.RECOMMEND_REDIS) -> None:
        self.configs = hosts_config
        self.used_config = self.configs[random.randint(0, len(self.configs) - 1)]
        self.redis_pool = redis.ConnectionPool(
            host=self.used_config['host'],
            port=self.used_config['port'],
            password=self.used_config['password'],
            socket_timeout=30,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        self.redis_conn = redis.StrictRedis(connection_pool=self.redis_pool)

    @classmethod
    def get_default(cls):
        global keepalive_redis_conn

        if not keepalive_redis_conn:
            keepalive_redis_conn = cls()
        else:
            try:
                keepalive_redis_conn.ping()
            except:
                keepalive_redis_conn.redis_conn.close()
                keepalive_redis_conn = None
        # reconnect
        if keepalive_redis_conn is None:
            keepalive_redis_conn = cls()

        return keepalive_redis_conn

    def get(self, key, *args):
        return self.redis_conn.get(key, *args)

    def ping(self):
        return self.redis_conn.ping()

    def mget(self, keys, *args):
        return self.redis_conn.mget(keys, *args)

    def setex(self, name, time, value):
        return self.redis_conn.setex(name, time, value)

    def lset(self, *args, **kwargs):
        return self.redis_conn.lset(*args, *kwargs)

    def lpop(self, name):
        return self.redis_conn.lpop(name)

    def rpush(self, *args, **kwargs):
        return self.redis_conn.rpush(*args, **kwargs)

    def llen(self, name):
        return self.redis_conn.llen(name)

    def lrange(self, name, start, end):
        return self.redis_conn.lrange(name, start, end)

    def delete(self, *args, **kwargs):
        return self.redis_conn.delete(*args, **kwargs)

    def mget(self, keys, *args):
        return self.redis_conn.mget(keys, *args)

    def zcard(self, key):
        return self.redis_conn.zcard(key)

    def zadd(self, name, mapping, nx=False, xx=False, ch=False, incr=False):
        return self.redis_conn.zadd(name, mapping, nx, xx, ch, incr)

    def zincr(self, name, amount, value):
        return self.redis_conn.zincrby(name, amount, value)

    def sismember(self, name, value):
        return self.redis_conn.sismember(name, value)

    def zrange(self, name, start, end, desc, withscores):
        return self.redis_conn.zrange(name, start, end, desc, withscores)

    def zpopmin(self, name, count):
        return self.redis_conn.zpopmin(name, count)

    def zrem(self, name, values):
        return self.redis_conn.zrem(name, values)

    def keys(self, pattern):
        return self.redis_conn.keys(pattern)

    def expires(self, key, ttl):
        return self.redis_conn.expire(key, ttl)

    def incr(self, name, amount=1):
        return self.redis_conn.incr(name, amount)

    def exists(self, *names) -> int:
        """ Returns the number of key
        :param names:
        :return: int
        """
        n = self.redis_conn.exists(*names)
        if isinstance(n, str):
            n = int(n)

        return n

