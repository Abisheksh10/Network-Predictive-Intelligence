---
description: Verify analytics grain invariant - check for duplicate (grid_id, timestamp)
---
Run this python command to verify star schema grain:
python -c "
import mysql.connector
conn = mysql.connector.connect(host='172.22.240.1', port=3306, user='root', password='root', database='telecom_warehouse')
cur = conn.cursor()
cur.execute('SELECT time_key, grid_id, COUNT(*) FROM fact_network_activity GROUP BY time_key, grid_id HAVING COUNT(*) > 1 LIMIT 5;')
dups = cur.fetchall()
cur.close()
conn.close()
if dups:
    print(f'GRAIN_VIOLATION_FAIL: Duplicate records found on (time_key, grid_id): {dups}')
    exit(1)
else:
    print('GRAIN_CHECK_PASS: Canonical grain strictly preserved (1 grid/hour).')
"
Report PASS or FAIL based on whether duplicate records exist.