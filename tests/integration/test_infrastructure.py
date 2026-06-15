import os
import redis


def test_redis_connection():
    """
    Verifies that the docker-compose infrastructure booted successfully
    and the Redis container is actively accepting connections.
    """
    # In CI/CD, docker forwards the port to localhost
    redis_host = os.getenv("REDIS_HOST", "localhost")

    # Attempt to connect to the newly spun up Redis container
    r = redis.Redis(host=redis_host, port=6379, db=0)

    # Ping the server. If it responds, the integration environment is healthy!
    assert r.ping() is True
