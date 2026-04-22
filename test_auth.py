import requests

login_url = 'https://mah-meteo.onrender.com/auth/login'
# Try to login and see the response status
credentials = {
    'username': 'geodis-lemeux',
    'password': 'Geodis60'
}

print(f'Final attempt at login {login_url} (JSON)...')
try:
    response = requests.post(login_url, json=credentials, timeout=30)
    print(f'Status Code: {response.status_code}')
    print(f'Response: {response.text}')
except Exception as e:
    print(f'Error: {e}')
