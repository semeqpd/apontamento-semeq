from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _sqlite_concurrency_pragmas(sender, connection, **kwargs):
    """SQLite em dev: WAL + busy_timeout para aguentar runserver
    multithread + importacoes concorrentes sem 'database is locked'."""
    if connection.vendor == 'sqlite':
        with connection.cursor() as cur:
            cur.execute('PRAGMA journal_mode=WAL;')
            cur.execute('PRAGMA busy_timeout=30000;')
            cur.execute('PRAGMA synchronous=NORMAL;')


class UserConfig(AppConfig):
    name = 'user'

    def ready(self):
        connection_created.connect(
            _sqlite_concurrency_pragmas, dispatch_uid='user.sqlite_wal'
        )
