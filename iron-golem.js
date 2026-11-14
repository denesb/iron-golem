async function start(id) {
    console.info(`Starting server #${id}`)

    response = await fetch(`/start/${id}`, { method: 'POST'});

    if (!response.ok) {
        //TODO:
    }

    console.info(`Started server #${id}`)

    const button = document.getElementById(`server-${id}`)
    button.classList.remove("btn-primary");
    button.classList.add("btn-success");
    button.innerHTML = "Stop";

    const status = document.getElementById(`server-${id}-status`)
    status.classList.remove("text-bg-secondary");
    status.classList.add("text-bg-success");
    status.innerHTML = "Running";
}

async function stop(id) {
    console.info(`Stopping server #${id}`)

    response = await fetch(`/stop/${id}`, { method: 'POST'});

    if (!response.ok) {
        //TODO
    }

    console.info(`Stopped server #${id}`)

    const button = document.getElementById(`server-${id}`)
    button.classList.remove("btn-success");
    button.classList.add("btn-primary");
    button.innerHTML = "Start";

    const status = document.getElementById(`server-${id}-status`)
    status.classList.remove("text-bg-success");
    status.classList.add("text-bg-secondary");
    status.innerHTML = "Not Running";
}

function toggleServer(event) {
    const id = event.target.id.split("-")[1]

    const button = document.getElementById(`server-${id}`)
    const isRunning = button.classList.contains("btn-success");

    if (isRunning) {
        stop(id);
    } else {
        start(id);
    }
}

async function postAndReload(url, params, button, id) {
    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Applying...';
    }

    const response = await fetch(url, { method: 'POST', body: new URLSearchParams(params) });

    if (!response.ok) {
        console.error(`POST ${url} failed: ${response.status} ${response.statusText}`);
    }

    // Reload to show the new configuration, keeping the details open.
    location.hash = `server-details-${id}`;
    location.reload();
}

function setGamemode(event, id, gamemode) {
    console.info(`Setting game mode of server #${id} to ${gamemode}`)
    postAndReload(`/gamemode/${id}`, { gamemode }, event.target, id);
}

function setNetwork(id, network) {
    console.info(`Setting network of server #${id} to ${network}`)
    for (const input of document.querySelectorAll(`#network-${id} input`)) {
        input.disabled = true;
    }
    postAndReload(`/network/${id}`, { network }, null, id);
}

const logTails = {};

async function pollLog(id) {
    const tail = logTails[id];
    if (!tail) {
        return;
    }

    try {
        const response = await fetch(`/log/${id}?offset=${tail.offset}`);
        if (response.ok) {
            const result = await response.json();
            const pre = document.getElementById(`server-log-${id}-content`);
            const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 5;
            if (result.reset) {
                pre.textContent = '';
            }
            pre.textContent += result.data;
            tail.offset = result.offset;
            if (atBottom) {
                pre.scrollTop = pre.scrollHeight;
            }
        }
    } catch (e) {
        console.error(`Failed to fetch log of server #${id}: ${e}`);
    }

    // The tail may have been stopped (or restarted) while the request was in flight.
    if (logTails[id] === tail) {
        tail.timer = setTimeout(() => pollLog(id), 1000);
    }
}

function startLogTail(id) {
    stopLogTail(id);
    logTails[id] = { offset: -1, timer: null };
    pollLog(id);
}

function stopLogTail(id) {
    const tail = logTails[id];
    if (tail) {
        clearTimeout(tail.timer);
        delete logTails[id];
    }
}

document.addEventListener('DOMContentLoaded', () => {
    for (const log of document.querySelectorAll('.server-log')) {
        const id = log.dataset.serverId;
        log.addEventListener('shown.bs.collapse', () => startLogTail(id));
        log.addEventListener('hidden.bs.collapse', () => stopLogTail(id));
    }

    // Re-open the server details after a reload (see postAndReload()).
    if (location.hash.startsWith('#server-details-')) {
        const details = document.querySelector(location.hash);
        if (details) {
            bootstrap.Collapse.getOrCreateInstance(details).show();
        }
    }
});

async function sendCommand(event, id) {
    event.preventDefault();
    const input = document.getElementById(`server-command-${id}`);
    const error = document.getElementById(`server-command-${id}-error`);
    const command = input.value.trim();
    if (!command) {
        return;
    }

    let message = null;
    try {
        const response = await fetch(`/command/${id}`, { method: 'POST', body: new URLSearchParams({ command }) });
        if (!response.ok) {
            message = (await response.json()).error;
        }
    } catch (e) {
        message = `${e}`;
    }

    if (message) {
        error.textContent = message;
        input.classList.add('is-invalid');
    } else {
        input.value = '';
        input.classList.remove('is-invalid');
        // Scroll to the bottom so the command's output is visible.
        const pre = document.getElementById(`server-log-${id}-content`);
        pre.scrollTop = pre.scrollHeight;
    }
}
