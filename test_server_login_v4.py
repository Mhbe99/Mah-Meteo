import subprocess
import time
import requests
import sys
import os
import signal

print('Starting uvicorn...')
with open('server_log.txt', 'w') as log_file:
    # Use direct list for Popen to avoid shell escaping issues if possible 
    # but Windows often needs a certain way to handle env.
    server_process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'meteo_saas.backend.main:app', '--host', '127.0.0.1', '--port', '8000'],
        stdout=log_file,
        stderr=log_file,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )

    print('Waiting for uvicorn to be ready...')
    start_time = time.time()
    success = False
    for i in range(25):
        try:
            # Check if root or docs might be available
            r = requests.get('http://127.0.0.1:8000/', timeout=1)
            print('Server is up!')
            success = True
            break
        except Exception:
            time.sleep(1)
            if i % 5 == 0:
                print(f'Still waiting... ({i}s)')
    
    if success:
        print('Testing login...')
        login_url = 'http://127.0.0.1:8000/auth/login'
        credentials = {'username': 'geodis-lemeux', 'password': 'Geodis60'}
        try:
            # Most FastAPI OAuth2 setups expect form data
            response = requests.post(login_url, data=credentials, timeout=10)
            print(f'Status Code: {response.status_code}')
            print('Response Content:')
            print(response.text)
        except Exception as e:
            print(f'Error during login request: {e}')
    else:
        print('Server failed to start within 25 seconds or returned error.')

    print('Killing the server...')
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(server_process.pid)], capture_output=True)
    else:
        server_process.terminate()
    
    print('--- Final Server Logs ---')
    try:
        with open('server_log.txt', 'r') as f:
            print(f.read())
    except Exception as e:
        print(f'Could not read logs: {e}')
