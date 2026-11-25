import os
import time

import httpx
import pymysql

BASE = 'http://127.0.0.1:8000/api/v1'
ACCOUNTS = [
    ('13810000001', 'PROSPECT', 'Test Prospect', None, 'New Customer'),
    ('13810000002', 'STUDENT', 'Test Student', None, 'Student'),
    ('13810000003', 'EMPLOYEE', 'Test Employee', 'ordinary employee', 'Singapore'),
    ('13810000004', 'MANAGER', 'Test Manager', 'president', 'Head Office'),
]
PASSWORD = 'Test@123456'


def wait_for_api():
    for _ in range(40):
        try:
            response = httpx.get('http://127.0.0.1:8000/health', timeout=2)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('Backend did not start on port 8000')


def create_accounts():
    conn = pymysql.connect(
        host='localhost',
        port=59000,
        user='root',
        password=os.environ.get("MYSQL_ROOT_PASSWORD", "change-me-in-local-env"),
        database='GuangdongEducationStudyAbroadProgram',
        charset='utf8mb4',
    )
    cursor = conn.cursor()
    normal_status = chr(27491) + chr(24120)
    for username, role, name, employee_role, department in ACCOUNTS:
        response = httpx.post(
            BASE + '/auth/register',
            json={
                'username': username,
                'password': PASSWORD,
                'real_name': name,
                'user_type': 'STUDENT',
                'contact_info': username,
            },
            timeout=15,
        )
        print('register', role, response.status_code)
        cursor.execute(
            'UPDATE sys_user SET user_type=%s,real_name=%s,phone=%s,status=%s,employee_role=%s,department=%s WHERE username=%s',
            (role, name, username, normal_status, employee_role, department, username),
        )
    conn.commit()
    for username, role, name, employee_role, department in ACCOUNTS:
        response = httpx.post(
            BASE + '/auth/login',
            json={'username': username, 'password': PASSWORD},
            timeout=15,
        )
        payload = response.json()
        print('login', role, response.status_code, payload.get('data', {}).get('user_type'))
    conn.close()


if __name__ == '__main__':
    wait_for_api()
    create_accounts()
