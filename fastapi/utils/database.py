import os
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=2,
            maxconn=20,
            host=os.environ.get('POSTGRES_HOST', 'postgres-db'),
            port=int(os.environ.get('POSTGRES_PORT', '5432')),
            database=os.environ.get('POSTGRES_DB', 'nxt_nms_db'),
            user=os.environ.get('POSTGRES_USER', 'nextrade'),
            password=os.environ.get('POSTGRES_PASSWORD', ''),
        )
        logger.info("DB connection pool initialized")
    return _pool


@contextmanager
def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
