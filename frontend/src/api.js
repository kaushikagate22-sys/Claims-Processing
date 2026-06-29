// Base URL for the API. In local split dev it defaults to the uvicorn port; in a
// production build set VITE_API_URL="" to use same-origin relative URLs (the API
// serves the frontend, so they share one origin). Using ?? keeps "" meaningful.
const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function handle(res) {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

// Read a Server-Sent-Events stream and yield each parsed JSON event.
async function* readSSE(res) {
  if (!res.ok || !res.body) throw new Error(`Stream failed (${res.status})`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let i;
    while ((i = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, i);
      buffer = buffer.slice(i + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (line) {
        try {
          yield JSON.parse(line.slice(5).trim());
        } catch (_) {}
      }
    }
  }
}

export const api = {
  base: BASE,

  health() {
    return fetch(`${BASE}/health`).then(handle);
  },

  listClaims() {
    return fetch(`${BASE}/claims`).then(handle).then((d) => d.claims || []);
  },

  getClaim(id) {
    return fetch(`${BASE}/claims/${id}`).then(handle);
  },

  getStats() {
    return fetch(`${BASE}/claims/stats`).then(handle);
  },

  // admin: policy + records
  getPolicy() {
    return fetch(`${BASE}/admin/policy`).then(handle);
  },
  savePolicy(text) {
    return fetch(`${BASE}/admin/policy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }).then(handle);
  },
  uploadPolicyFile(file) {
    const form = new FormData(); form.append("file", file);
    return fetch(`${BASE}/admin/policy/upload`, { method: "POST", body: form }).then(handle);
  },
  getRecords() {
    return fetch(`${BASE}/admin/records`).then(handle);
  },

  getMasters() {
    return fetch(`${BASE}/admin/masters`).then(handle);
  },
  uploadMaster(kind, file) {
    const form = new FormData(); form.append("file", file);
    return fetch(`${BASE}/admin/masters/${kind}`, { method: "POST", body: form }).then(handle);
  },
  uploadPolicies(file) {
    const form = new FormData(); form.append("file", file);
    return fetch(`${BASE}/admin/records/policies`, { method: "POST", body: form }).then(handle);
  },
  uploadHistory(file) {
    const form = new FormData(); form.append("file", file);
    return fetch(`${BASE}/admin/records/history`, { method: "POST", body: form }).then(handle);
  },

  getTypes() {
    return fetch(`${BASE}/admin/types`).then(handle);
  },
  saveTypeFields(type, fields) {
    return fetch(`${BASE}/admin/types/fields`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, fields }),
    }).then(handle);
  },

  saveTypeRules(type, checks, config) {
    return fetch(`${BASE}/admin/types/rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, checks, config }),
    }).then(handle);
  },
  saveTypeVisual(type, visual_checks) {
    return fetch(`${BASE}/admin/types/visual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, visual_checks }),
    }).then(handle);
  },

  // streaming runs (live pipeline) — async generators of events
  async *streamText(text) {
    const res = await fetch(`${BASE}/claims/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    yield* readSSE(res);
  },

  async *streamFile(file, images = []) {
    const form = new FormData();
    form.append("file", file);
    (images || []).forEach((img) => form.append("images", img));
    const res = await fetch(`${BASE}/claims/stream/upload`, {
      method: "POST",
      body: form,
    });
    yield* readSSE(res);
  },
};
