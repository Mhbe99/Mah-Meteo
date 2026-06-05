import subprocess
import time
import requests
import sys
import os

print('Starting uvicorn...')
with open('server_log.txt', 'w') as log_file:
    # Use 'uvicorn' directly if it's in the PATH, otherwise we might need the full path
    server_process = subprocess.Popen(
        ['uvicorn', 'meteo_saas.backend.main:app', '--host', '127.0.0.1', '--port', '8000'],
        stdout=log_file,
        stderr=log_file,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
        shell=True # Try with shell=True for 'uvicorn' command
    )

    print('Waiting for uvicorn to be ready...')
    success = False
    for i in range(25):
        try:
            r = requests.get('http://127.0.0.1:8000/docs', timeout=1)
            print('Server is up!')
            success = True
            break
        except Exception:
            time.sleep(1)
            if i % 2 == 0: print(f'Waiting... {i}s')
    
    if success:
        print('Testing login...')
        login_url = 'http://127.0.0.1:8000/auth/login'
        credentials = {
            'username': os.getenv('TEST_USERNAME') or os.getenv('INIT_CLIENT_USERNAME', 'service-meteo'),
            'password': os.getenv('TEST_PASSWORD') or os.getenv('INIT_CLIENT_PASSWORD', '')
        }
        try:
            # Login form usually expects form data
            response = requests.post(login_url, data=credentials, timeout=10)
            print(f'Status Code: {response.status_code}')
            print('Response Content:')
            print(response.text)
        except Exception as e:
            print(f'Error during login request: {e}')
    else:
        print('Server failed to start.')

    print('Cleaning up...')
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(server_process.pid)], capture_output=True)
    else:
        server_process.terminate()

    print('--- Logs ---')
    with open('server_log.txt', 'r') as f:
        print(f.read())
