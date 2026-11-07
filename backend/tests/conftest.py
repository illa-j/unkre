import os

for name, value in {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_DB_PORT": "5432",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_KEY_TIMEDELTA_MINUTES": "15",
    "REFRESH_KEY_TIMEDELTA_MINUTES": "43200",
    "SECRET_KEY_ACCESS": "test-access-" + "a" * 32,
    "SECRET_KEY_REFRESH": "test-refresh-" + "b" * 32,
    "SECURITY_REDIS_ENABLED": "false",
    "SECURITY_ROUTE_RATE_LIMIT_ENABLED": "false",
    "RUNPOD_ENDPOINTS": "",
}.items():
    os.environ.setdefault(name, value)
