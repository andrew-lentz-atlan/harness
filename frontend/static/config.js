// config.js — sidebar config form. Loads from /api/config, saves on click.

const $ = (sel) => document.querySelector(sel);

const els = {
    backend: $("#cfg-backend"),
    backendDesc: $("#cfg-backend-desc"),
    modelName: $("#cfg-model-name"),
    temp: $("#cfg-temp"),
    tempVal: $("#cfg-temp-value"),
    topp: $("#cfg-topp"),
    toppVal: $("#cfg-topp-value"),
    maxTokens: $("#cfg-maxtokens"),
    system: $("#cfg-system"),
    style: $("#cfg-style"),
    styleDesc: $("#cfg-style-desc"),
    toolsEnabled: $("#cfg-tools-enabled"),
    toolsList: $("#cfg-tools-list"),
    save: $("#cfg-save"),
    reset: $("#cfg-reset"),
    status: $("#cfg-status"),
    rawBlock: $("#config-raw"),
};

const BACKEND_DESCRIPTIONS = {
    "litellm": "Hosted OpenAI-compatible proxy. Reads LITELLM_BASE_URL + LITELLM_API_KEY from env.",
    "llama-server": "Local llama.cpp llama-server. Reads LLAMA_SERVER_URL from env (default localhost:8080).",
};

let state = {
    config: null,
    presets: [],
    available_tools: [],
    available_backends: ["litellm", "llama-server"],
};

function setStatus(msg, isError = false) {
    els.status.textContent = msg || "";
    els.status.style.color = isError ? "var(--error)" : "var(--muted)";
}

function render() {
    const c = state.config;

    // Backend dropdown
    els.backend.innerHTML = "";
    for (const b of state.available_backends) {
        const o = document.createElement("option");
        o.value = b;
        o.textContent = b;
        els.backend.appendChild(o);
    }
    els.backend.value = c.backend ?? "litellm";
    updateBackendDesc();

    els.modelName.value = c.model?.name ?? "";
    els.temp.value = c.model?.temperature ?? 0.7;
    els.tempVal.textContent = (+els.temp.value).toFixed(2);
    els.topp.value = c.model?.top_p ?? 0.95;
    els.toppVal.textContent = (+els.topp.value).toFixed(2);
    els.maxTokens.value = c.model?.max_tokens ?? 1024;
    els.system.value = c.system_prompt ?? "";

    // Reasoning style dropdown — default + presets
    els.style.innerHTML = "";
    const opts = [{ id: "default", name: "Default", description: "Just the system prompt above." }, ...state.presets];
    for (const p of opts) {
        const o = document.createElement("option");
        o.value = p.id;
        o.textContent = p.name || p.id;
        els.style.appendChild(o);
    }
    els.style.value = c.reasoning_style ?? "default";
    updateStyleDesc();

    els.toolsEnabled.checked = !!c.tools?.enabled;

    // Tool checkboxes — every available tool, ticked if in allowlist.
    const allow = new Set(c.tools?.allowlist ?? []);
    els.toolsList.innerHTML = "";
    for (const t of state.available_tools) {
        const id = `tool-${t}`;
        const wrap = document.createElement("label");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.id = id;
        cb.dataset.tool = t;
        cb.checked = allow.has(t);
        wrap.appendChild(cb);
        wrap.appendChild(document.createTextNode(t));
        els.toolsList.appendChild(wrap);
    }

    els.rawBlock.textContent = JSON.stringify(c, null, 2);
}

function updateStyleDesc() {
    const id = els.style.value;
    const p = state.presets.find((x) => x.id === id);
    els.styleDesc.textContent = p?.description ?? "";
}

function updateBackendDesc() {
    els.backendDesc.textContent = BACKEND_DESCRIPTIONS[els.backend.value] ?? "";
}

function collect() {
    const checked = [...els.toolsList.querySelectorAll("input[type=checkbox]:checked")].map((el) => el.dataset.tool);
    return {
        backend: els.backend.value,
        model: {
            name: els.modelName.value.trim(),
            temperature: +els.temp.value,
            top_p: +els.topp.value,
            max_tokens: +els.maxTokens.value,
        },
        system_prompt: els.system.value,
        reasoning_style: els.style.value,
        tools: {
            enabled: els.toolsEnabled.checked,
            allowlist: checked,
        },
        memory: state.config?.memory ?? { enabled: false },
    };
}

async function load() {
    setStatus("Loading…");
    const res = await fetch("/api/config");
    if (!res.ok) {
        setStatus("Failed to load config", true);
        return;
    }
    const data = await res.json();
    state = { ...state, ...data };
    render();
    setStatus("Loaded");
    setTimeout(() => setStatus(""), 800);
}

async function save() {
    const config = collect();
    setStatus("Saving…");
    els.save.disabled = true;
    try {
        const res = await fetch("/api/config", {
            method: "PUT",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ config }),
        });
        if (!res.ok) {
            const err = await res.text();
            setStatus(`Save failed: ${err}`, true);
            return;
        }
        const data = await res.json();
        state.config = data.config;
        render();
        setStatus("Saved. New chats will use these settings.");
    } finally {
        els.save.disabled = false;
    }
}

els.temp.addEventListener("input", () => { els.tempVal.textContent = (+els.temp.value).toFixed(2); });
els.topp.addEventListener("input", () => { els.toppVal.textContent = (+els.topp.value).toFixed(2); });
els.style.addEventListener("change", updateStyleDesc);
els.backend.addEventListener("change", updateBackendDesc);
els.save.addEventListener("click", save);
els.reset.addEventListener("click", load);

window.harnessConfig = { load };
load();
