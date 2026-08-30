const BASE = 'http://localhost:8000/api';

// Compute HMAC-SHA256 signature for webhook payloads using Web Crypto API
async function signPayload(payloadStr) {
  const secret = import.meta.env.VITE_WEBHOOK_SECRET || '';
  if (!secret) return 'sha256=demo';
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(payloadStr));
  const hex = Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, '0')).join('');
  return `sha256=${hex}`;
}

export const api = {
  getRepos: () => fetch(`${BASE}/repos`).then(r => r.json()),

  getBuilds: (repoId) => fetch(`${BASE}/builds?repo_id=${repoId}`).then(r => r.json()),

  getBuild: (runId) => fetch(`${BASE}/builds/${runId}`).then(r => {
    if (!r.ok) return null;
    return r.json();
  }),

  getBuildPrediction: (runId) => fetch(`${BASE}/builds/${runId}/prediction`).then(r => {
    if (!r.ok) return null;
    return r.json();
  }),

  predict: (payload) => fetch(`${BASE}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(r => r.json()),

  getLatestPrediction: (repoId) =>
    fetch(`${BASE}/repos/${repoId}/latest-prediction`).then(r => {
      if (!r.ok) return null;
      return r.json();
    }),

  getAccuracy: (repoId) => fetch(`${BASE}/repos/${repoId}/accuracy`).then(r => r.json()),

  getStats: (repoId) => fetch(`${BASE}/repos/${repoId}/stats`).then(r => r.json()),

  getHotpaths: (repoId) => fetch(`${BASE}/repos/${repoId}/hotpaths`).then(r => r.json()),

  triggerDemo: async (payload) => {
    const body = JSON.stringify(payload);
    const signature = await signPayload(body);
    return fetch(`${BASE}/webhook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-GitHub-Event': 'push',
        'X-Hub-Signature-256': signature,
      },
      body,
    }).then(r => r.json());
  },
};
