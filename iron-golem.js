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

document.addEventListener('DOMContentLoaded', () => {
    // Re-open the server details after a reload (see postAndReload()).
    if (location.hash.startsWith('#server-details-')) {
        const details = document.querySelector(location.hash);
        if (details) {
            bootstrap.Collapse.getOrCreateInstance(details).show();
        }
    }
});
