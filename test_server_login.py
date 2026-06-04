import subprocess
import time
import requests
import sys
import os

# 1. Start uvicorn
print('Starting uvicorn...')
server_process = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'meteo_saas.backend.main:app', '--host', '127.0.0.1', '--port', '8000'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# 2. Wait 5 seconds for startup
print('Waiting 5 seconds for startup...')
time.sleep(5)

# 3. Test POST http://127.0.0.1:8000/auth/login
print('Testing login...')
login_url = 'http://127.0.0.1:8000/auth/login'
credentials = {
    'username': os.getenv('TEST_USERNAME') or os.getenv('INIT_CLIENT_USERNAME', 'service-meteo'),
    'password': os.getenv('TEST_PASSWORD') or os.getenv('INIT_CLIENT_PASSWORD', '')
}

try:
    # Most FastAPI OAuth2/Login forms use Form data (x-www-form-urlencoded)
    # If it fails, we can try JSON. Let's try Form data first as it's standard for OAuth2PasswordRequestForm
    response = requests.post(login_url, data=credentials, timeout=10)
    
    # 4. Show the response status and content
    print(f'Status Code: {response.status_code}')
    print('Response Content:')
    print(response.text)
except Exception as e:
    print(f'Error during request: {e}')

# 5. Kill the server
print('Killing the server...')
server_process.terminate()
try:
    server_process.wait(timeout=5)
except subprocess.TimeoutExpired:
    server_process.kill()
print('Server stopped.')
