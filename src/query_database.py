"""Read-only local diagnostic command; importing it has no database side effects."""
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
from src.config import Settings


def main():
    with duckdb.connect(str(Settings.from_env().db_path), read_only=True) as con:
        print(con.execute('SHOW TABLES').fetchdf())
        print(con.execute('SELECT exception_type, severity, COUNT(*) AS break_count FROM trade_breaks GROUP BY ALL').fetchdf())


if __name__ == '__main__':
    main()
