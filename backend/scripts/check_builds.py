import urllib.request, json
r = json.loads(urllib.request.urlopen('http://localhost:8000/api/builds?repo_id=pipeline-prophet-demo').read())
print(f'Got {len(r)} builds')
for b in r[:5]:
    rid = str(b.get('run_id') or b.get('_id') or '?')[:12]
    status = b.get('status', 'MISSING')
    outcome = b.get('outcome', 'MISSING')
    commit = str(b.get('commit_sha') or '?')[:8]
    author = b.get('author', '?')
    print(f'  run_id={rid}  status={status}  outcome={outcome}  commit={commit}  author={author}')
