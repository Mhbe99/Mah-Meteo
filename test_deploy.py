import requests
import time
import sys

BASE_URL = 'https://mah-meteo.onrender.com'
LOGIN_DATA = {'username': 'geodis-lemeux', 'password': 'Geodis60'}

def test_deploy():
    token = None
    
    # User said wait 90 seconds for Render to redeploy
    print('Waiting 90 seconds for redeploy...')
    time.sleep(90)
    
    for i in range(4): # First attempt + 3 retries
        if i > 0:
            print(f'Retry {i}/3 in 30s...')
            time.sleep(30)
        
        try:
            # Note: Health endpoint doesn't exist? We'll try it but focus on Login
            print(f'Attempt {i+1}: Checking health...')
            h = requests.get(f'{BASE_URL}/api/health', timeout=10)
            print(f'Health status: {h.status_code}')
            
            print(f'Attempt {i+1}: Logging in...')
            # Based on main.py search, login is at /auth/login
            r = requests.post(f'{BASE_URL}/auth/login', json=LOGIN_DATA, timeout=30)
            print(f'Login status: {r.status_code}')
            
            if r.status_code == 200:
                token = r.json().get('access_token')
                print('Login successful')
                break
            elif r.status_code == 500:
                print('Server returned 500, might still be deploying.')
                continue
            elif r.status_code == 404:
                print('Endpoint not found (404), might be wrong URL path or still deploying/starting.')
                continue
            else:
                print(f'Unexpected login status: {r.status_code}')
                continue
        except Exception as e:
            print(f'Error during attempt {i+1}: {e}')
            continue
            
    if not token:
        print('Failed to obtain token after retries.')
        return

    print('Testing endpoint: POST /api/admin/approve/999')
    headers = {'Authorization': f'Bearer {token}'}
    try:
        res = requests.post(f'{BASE_URL}/api/admin/approve/999', headers=headers, timeout=10)
        print(f'Approve response: {res.status_code}')
        print(res.text)
    except Exception as e:
        print(f'Error calling approve: {e}')

test_deploy()
