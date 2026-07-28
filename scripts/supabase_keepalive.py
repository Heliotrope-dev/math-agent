import re, sys, requests

with open('/root/math-agent/.streamlit/secrets.toml') as f:
    txt = f.read()
d = dict(re.findall(r'^(\w+)\s*=\s*"([^"]*)"', txt, re.M))
key = d.get('SUPABASE_KEY', '')
base = d.get('SUPABASE_URL', '').rstrip('/')
if not key or not base:
    print('missing SUPABASE_URL/SUPABASE_KEY, skip')
    sys.exit(1)

headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
try:
    r = requests.get(f'{base}/rest/v1/users', headers=headers, params={'select': 'email', 'limit': '1'}, timeout=15)
    print(f'keepalive ping: status={r.status_code}')
except Exception as e:
    print(f'keepalive ping failed: {e!r}')
    sys.exit(1)
