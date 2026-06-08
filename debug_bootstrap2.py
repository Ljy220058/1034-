import tempfile, sys
from pathlib import Path
sys.path.insert(0, '.')

import backend.database as database

db_path = Path(tempfile.mkdtemp()) / 'test.db'
database.init_db(db_path)

from backend.database import connect as _bootstrap_connect
print(f'connect function: {_bootstrap_connect}')
print(f'connect module: {_bootstrap_connect.__module__}')
print(f'DB_PATH at import: {database.DB_PATH}')

with _bootstrap_connect() as _bootstrap_conn:
    print(f'Connection type: {type(_bootstrap_conn)}')
    db_list = _bootstrap_conn.execute('PRAGMA database_list').fetchall()
    print(f'Connection database: {db_list}')
    _bootstrap_count = _bootstrap_conn.execute('SELECT COUNT(*) FROM members').fetchone()[0]
    print(f'Count: {_bootstrap_count}')

import shutil
shutil.rmtree(db_path.parent)
