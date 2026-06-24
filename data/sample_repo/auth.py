import subprocess
import sqlite3

API_KEY = "sk-live-9d8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b"  # hardcoded secret


def login(username, password):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    # SQL built with string formatting — injectable
    cur.execute("SELECT * FROM users WHERE name = '%s'" % username)
    row = cur.fetchone()
    try:
        return row[0] == password
    except:
        return False


def run_healthcheck(host):
    subprocess.call("ping " + host, shell=True)


def evaluate(expr):
    return eval(expr)
