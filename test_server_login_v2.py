import subprocess
import time
import requests
import sys
import os

print('Starting uvicorn...')
# Use a log file to see what's happening
with open('server_log.txt', 'w') as log_file:
    server_process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'meteo_saas.backend.main:app', '--host', '127.0.0.1', '--port', '8000'],
        stdout=log_file,
        stderr=log_file,
        text=True
    )

    print('Waiting 10 seconds for startup...')
    time.sleep(10)

    print('Testing login...')
    login_url = 'http://127.0.0.1:8000/auth/login'
    credentials = {
        'username': os.getenv('TEST_USERNAME') or os.getenv('INIT_CLIENT_USERNAME', 'service-meteo'),
        'password': os.getenv('TEST_PASSWORD') or os.getenv('INIT_CLIENT_PASSWORD', '')
    }

    try:
        response = requests.post(login_url, data=credentials, timeout=10)
        print(f'Status Code: {response.status_code}')
        print('Response Content:')
        print(response.text)
    except Exception as e:
        print(f'Error during request: {e}')
        # Print logs if error
        print('--- Server Logs ---')
        try:
            with open('server_log.txt', 'r') as f:
                print(f.read())
        except:
            pass

    print('Killing the server...')
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except:
        server_process.kill()
    print('Server stopped.')
