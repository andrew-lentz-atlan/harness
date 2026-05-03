// chat.js — chat panel + SSE streaming + trace tab + tab switcher.

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const sessionIdEl = document.getElementById("session-id");
const newSessionBtn = document.getElementById("new-session");
const traceEventsEl = document.getElementById("trace-events");
const traceRefreshBtn = document.getElementById("trace-refresh");
const traceClearBtn = document.getElementById("trace-clear");

let sessionId = null;

// ---------------------------------------------------------------- tabs

document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        const target = tab.dataset.tab;
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        document.getElementById(`tab-${target}`).classList.add("active");
        if (target === "trace") refreshTrace();
        if (target === "config") window.harnessConfig?.load();
    });
});

// ---------------------------------------------------------------- chat rendering

function renderMessage(role, content, meta) {
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = role;
    el.appendChild(label);
    const body = document.createElement("div");
    body.textContent = content;
    el.appendChild(body);
    if (meta) {
        const m = document.createElement("div");
        m.className = "meta";
        m.textContent = meta;
        el.appendChild(m);
    }
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
}

function setSessionId(id) {
    sessionId = id;
    sessionIdEl.textContent = id ? `session: ${id}` : "";
}

newSessionBtn.addEventListener("click", async () => {
    if (sessionId) {
        await fetch(`/api/chat/reset?session_id=${encodeURIComponent(sessionId)}`, { method: "POST" });
    }
    setSessionId(null);
    messagesEl.innerHTML = "";
    traceEventsEl.innerHTML = "";
});

// ---------------------------------------------------------------- SSE streaming
//
// EventSource only supports GET, but our endpoint is POST. So we use
// fetch() and parse the SSE stream by hand.

async function streamChat(message) {
    const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
    });
    if (!res.ok || !res.body) {
        renderMessage("error", `Request failed: ${res.status} ${res.statusText}`);
        return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        // Normalize CRLF → LF up front so our separator search works
        // regardless of which line ending the server sends.
        buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

        // SSE frames are separated by blank lines.
        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
            const frame = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            handleFrame(frame);
        }
    }
}

function handleFrame(frame) {
    let event = "message";
    const dataLines = [];
    for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    let data;
    try {
        data = JSON.parse(dataLines.join("\n"));
    } catch {
        return;
    }
    onEvent(event, data);
}

function onEvent(event, data) {
    switch (event) {
        case "session":
            setSessionId(data.session_id);
            break;
        case "assistant": {
            const tcCount = data.tool_calls?.length ?? 0;
            let body = data.content || (tcCount ? `(calling ${tcCount} tool${tcCount > 1 ? "s" : ""}…)` : "");
            const meta = `${data.latency_ms} ms · ${data.usage?.total_tokens ?? "?"} tok`;
            renderMessage("assistant", body, meta);
            break;
        }
        case "tool_call":
            renderMessage("tool", `→ ${data.name}(${JSON.stringify(data.args)})`);
            break;
        case "tool_result":
            renderMessage("tool", `← ${truncate(data.result, 800)}`);
            break;
        case "error":
            renderMessage("error", data.message);
            break;
        case "done":
            // No-op. The final assistant message already rendered.
            break;
    }
}

function truncate(s, n) {
    if (s == null) return "";
    s = String(s);
    return s.length > n ? s.slice(0, n) + "…" : s;
}

// ---------------------------------------------------------------- send

formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = inputEl.value.trim();
    if (!message) return;
    inputEl.value = "";
    renderMessage("user", message);
    try {
        await streamChat(message);
    } catch (err) {
        renderMessage("error", String(err));
    }
});

inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        formEl.requestSubmit();
    }
});

// ---------------------------------------------------------------- trace

async function refreshTrace() {
    if (!sessionId) {
        traceEventsEl.innerHTML = '<p class="muted">No session yet — send a message first.</p>';
        return;
    }
    const res = await fetch(`/api/trace/${encodeURIComponent(sessionId)}`);
    if (!res.ok) {
        traceEventsEl.innerHTML = `<p class="muted">Failed to load trace.</p>`;
        return;
    }
    const data = await res.json();
    if (!data.events.length) {
        traceEventsEl.innerHTML = '<p class="muted">No events yet.</p>';
        return;
    }
    traceEventsEl.innerHTML = "";
    for (const ev of data.events) {
        const card = document.createElement("div");
        card.className = `trace-event kind-${ev.kind}`;
        const head = document.createElement("header");
        const kind = document.createElement("span");
        kind.className = "kind";
        kind.textContent = ev.kind;
        const ts = document.createElement("span");
        ts.className = "muted";
        ts.textContent = new Date(ev.ts * 1000).toLocaleTimeString();
        head.appendChild(kind);
        head.appendChild(ts);
        card.appendChild(head);

        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(ev.payload, null, 2);
        card.appendChild(pre);
        traceEventsEl.appendChild(card);
    }
}

traceRefreshBtn.addEventListener("click", refreshTrace);
traceClearBtn.addEventListener("click", async () => {
    if (!sessionId) return;
    await fetch(`/api/trace/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    refreshTrace();
});
