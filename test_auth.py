import os
import requests

login_url = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com") + '/auth/login'
# Try to login and see the response status
credentials = {
    'username': os.getenv('TEST_USERNAME') or os.getenv('INIT_CLIENT_USERNAME', 'service-meteo'),
    'password': os.getenv('TEST_PASSWORD') or os.getenv('INIT_CLIENT_PASSWORD', '')
}

print(f'Final attempt at login {login_url} (JSON)...')
try:
    response = requests.post(login_url, json=credentials, timeout=30)
    print(f'Status Code: {response.status_code}')
    print(f'Response: {response.text}')
except Exception as e:
    print(f'Error: {e}')
