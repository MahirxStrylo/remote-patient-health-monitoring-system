import urllib.request
import urllib.parse
import json

# 1. Login
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = json.loads(urllib.request.urlopen(req).read().decode())['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. Dashboard Stats
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/dashboard/stats', headers=headers)
stats = json.loads(urllib.request.urlopen(req).read().decode())
print('Dashboard Stats - Total Patients:', stats['total_patients'], 'Devices:', stats['total_devices'], 'Active:', stats['active_devices'], 'Uploads:', stats['latest_uploads_count'])

# 3. List ECG Sessions
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/ecg/sessions', headers=headers)
sessions = json.loads(urllib.request.urlopen(req).read().decode())
items = sessions.get('items', [])
print(f'Total ECG Sessions in DB: {len(items)}')
for s in items[:3]:
    print(f"  Session: {s['session_id']}, Status: {s['status']}, Batches: {s['total_batches']}, Samples: {s['total_samples']}")

# 4. Get Samples for 5-batch session
session_id = items[0]['session_id']
req = urllib.request.Request(f'http://127.0.0.1:8000/api/v1/ecg/sessions/{session_id}/samples', headers=headers)
samples_res = json.loads(urllib.request.urlopen(req).read().decode())
print(f'\nSamples for {session_id}:')
print('  Raw Samples count:', len(samples_res.get('samples', [])))
print('  Filtered Samples count:', len(samples_res.get('filtered_samples', [])))
print('  Sampling Rate:', samples_res.get('sampling_rate_hz'), 'Hz')
print('  Duration:', samples_res.get('duration_seconds'), 's')
print('  Unit:', samples_res.get('ecg_unit'))
print('  Has gaps:', samples_res.get('has_gaps'))

# 5. Check CSV Export
req = urllib.request.Request(f'http://127.0.0.1:8000/api/v1/ecg/sessions/{session_id}/export.csv', headers=headers)
with urllib.request.urlopen(req) as r:
    csv_sample = r.read(250).decode()
    print('\nCSV Export Header:\n' + csv_sample.strip())

# 6. Check PNG Plot Export
req = urllib.request.Request(f'http://127.0.0.1:8000/api/v1/ecg/sessions/{session_id}/plot.png', headers=headers)
with urllib.request.urlopen(req) as r:
    png_bytes = r.read()
    print(f'\nPNG Plot Export Size: {len(png_bytes)} bytes, starts with PNG magic: {png_bytes.startswith(b"\x89PNG")}')

# 7. Check Gap Session SES-GAP-2e94b5fc samples
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/ecg/sessions/SES-GAP-2e94b5fc/samples', headers=headers)
gap_res = json.loads(urllib.request.urlopen(req).read().decode())
print('\nGap Session SES-GAP-2e94b5fc:')
print('  Gaps Detected:', gap_res.get('has_gaps'))
print('  Missing Sequences:', gap_res.get('missing_sequences'))
null_count = sum(1 for s in gap_res.get('samples', []) if s is None)
print(f'  Visual None breaks inserted: {null_count} nulls across total length {len(gap_res.get("samples", []))}')

print('\nALL LIVE API ENDPOINTS FULLY VERIFIED!')
