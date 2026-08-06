import urllib.request, urllib.error, json, time
paths=['/health','/agents','/status']
for path in paths:
    url='http://127.0.0.1:8001'+path
    print('PATH', path)
    try:
        start = time.time()
        with urllib.request.urlopen(url, timeout=15) as r:
            data = r.read().decode('utf-8')
        elapsed = time.time() - start
        print('OK', elapsed)
        print(data[:1000])
    except Exception as e:
        import traceback
        traceback.print_exc()
    print('---')