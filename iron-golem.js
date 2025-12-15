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
