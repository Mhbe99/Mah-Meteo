import subprocess
import time
import requests
import sys
import psutil
import os

def kill_proc_tree(pid, including_parent=True):
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    for child in children:
        child.kill()
    if including_parent:
        parent.kill()

print('Starting uvicorn...')
with open('server_log.txt', 'w') as log_file:
    # Use shell=True or direct executable to ensure it starts correctly on Windows
    server_process = subprocess.Popen(
        f'"{sys.executable}" -m uvicorn meteo_saas.backend.main:app --host 127.0.0.1 --port 8000',
        stdout=log_file,
        stderr=log_file,
        shell=True
    )

    print('Waiting for uvicorn to be ready...')
    start_time = time.time()
    success = False
    while time.time() - start_time < 20:
        try:
            r = requests.get('http://127.0.0.1:8000/', timeout=1)
            print('Server is up!')
            success = True
            break
        except:
            time.sleep(1)
    
    if success:
        print('Testing login...')
        login_url = 'http://127.0.0.1:8000/auth/login'
        # Try both form and JSON if needed, but start with Form for OAuth2
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
            print(f'Error during login request: {e}')
    else:
        print('Server failed to start within 20 seconds.')

    print('Killing the server and its children...')
    try:
        kill_proc_tree(server_process.pid)
    except Exception as e:
        print(f'Kill error: {e}')
    
    print('--- Final Server Logs ---')
    try:
        with open('server_log.txt', 'r') as f:
            print(f.read())
    except:
        pass
