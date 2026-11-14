#!/usr/bin/env python3

import argparse
import bottle
import html
import json
import logging
import pathlib
import subprocess


logger = logging.getLogger('iron-golem')

root = pathlib.Path(__file__).resolve().parent

servers = {}
last_id = 0

# Network name -> interface name, filled in from the command line in main.
networks = {}
network_labels = {
    'all': 'All interfaces',
    'lan': 'Local network',
    'vpn': 'VPN',
}


def next_id():
    global last_id
    id = last_id
    last_id += 1
    return id


class minecraft_server:
    def __init__(self, path, config):
        self.id = next_id()
        self.path = path.resolve()
        self.config = config

        self._process = None
        self._logfile = None

    @property
    def ip(self):
        ip = self.config['server-ip']
        if ip == '':
            return '*'
        return ip

    @property
    def is_running(self):
        return self._process is not None and self._process.poll() is None

    @property
    def gamemode(self):
        mode = self.config.get('gamemode', 'survival')
        # Old server versions use numeric game modes.
        return {'0': 'survival', '1': 'creative'}.get(mode, mode)

    @property
    def network(self):
        """The network the server listens on: 'all', 'lan', 'vpn' or None (custom address)."""
        ip = self.config.get('server-ip', '')
        if ip == '':
            return 'all'
        for name in networks:
            if ip in interface_addresses().get(networks[name], []):
                return name
        return None

    @property
    def listen_addresses(self):
        ip = self.config.get('server-ip', '')
        if ip != '':
            return [ip]
        return [f'{addr} ({iface})' for iface, addrs in interface_addresses().items() for addr in addrs]

    @property
    def log_path(self):
        return self.path / 'server.log'

    @property
    def port(self):
        return int(self.config['server-port'])

    def start(self):
        self._logfile = open(self.log_path, 'w')
        args = [
            '/usr/bin/java',
            '-Xmx1024M',
            '-Xms1024M',
            '-jar',
            str(self.path.joinpath('server.jar')),
            'nogui',
        ]
        self._process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=self._logfile, stderr=self._logfile,
                                         cwd=self.path, text=True)

    def send_command(self, command):
        """Send a command to the server console, return False if the server is not running."""
        if not self.is_running:
            return False
        # Echo the command into the log, so it is visible next to its output.
        self._logfile.write(f'> {command}\n')
        self._logfile.flush()
        try:
            self._process.stdin.write(command + '\n')
            self._process.stdin.flush()
        except BrokenPipeError:
            return False
        return True

    def stop(self):
        if self._process is None:
            return
        # The server saves the world on SIGTERM, give it time to finish.
        self._process.terminate()
        try:
            self._process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            logger.warning(f"server {self.path.name} did not stop in time, killing it")
            self._process.kill()
            self._process.wait()
        self._process = None
        self._logfile.close()
        self._logfile = None

    def update_config(self, changes):
        """Change the given keys in server.properties, preserving the rest of the file.

        If the server is running, it is stopped before and restarted after the change.
        """
        was_running = self.is_running
        if was_running:
            self.stop()

        config_file = self.path / 'server.properties'
        remaining = dict(changes)
        lines = []
        for line in config_file.read_text().splitlines():
            stripped = line.strip()
            if stripped and stripped[0] != '#' and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in remaining:
                    line = f'{key}={remaining.pop(key)}'
            lines.append(line)
        lines += [f'{key}={value}' for key, value in remaining.items()]
        config_file.write_text('\n'.join(lines) + '\n')

        self.config = parse_config(config_file)

        if was_running:
            self.start()


def interface_addresses():
    """Return a dict of interface name -> list of IPv4 addresses."""
    out = subprocess.run(['ip', '-j', '-4', 'addr', 'show'], capture_output=True, text=True, check=True).stdout
    result = {}
    for iface in json.loads(out):
        addrs = [a['local'] for a in iface.get('addr_info', []) if a.get('family') == 'inet']
        if addrs:
            result[iface['ifname']] = addrs
    return result


def network_address(network):
    """Return the address to listen on for the given network, '' means all, None means unavailable."""
    if network == 'all':
        return ''
    addrs = interface_addresses().get(networks.get(network), [])
    return addrs[0] if addrs else None


def default_route_interface():
    out = subprocess.run(['ip', '-j', 'route', 'show', 'default'], capture_output=True, text=True).stdout
    try:
        return json.loads(out)[0]['dev']
    except (ValueError, IndexError, KeyError):
        return None



def parse_config(config_file):
    config = {}
    with open (config_file, 'r') as f:
        for l in f:
            l = l.strip()

            if not l:
                continue
            if l[0] == '#':
                continue

            key, value = l.split('=', 1)

            key = key.replace('"', '')

            config[key] = value.replace('"', '')

    return config


def render_server(server):
    if server.is_running:
        button_class = "success"
        button_text = "Stop"
        status_class = "success"
        status_text = "Running"
    else:
        button_class = "primary"
        button_text = "Start"
        status_class = "secondary"
        status_text = "Not Running"

    addresses = '<br>'.join(f'{html.escape(addr)}' for addr in server.listen_addresses)

    gamemode = server.gamemode
    other_gamemode = 'survival' if gamemode == 'creative' else 'creative'

    network_buttons = []
    current_network = server.network
    for name, label in network_labels.items():
        checked = 'checked' if name == current_network else ''
        disabled = 'disabled' if network_address(name) is None else ''
        network_buttons.append(f'''<input type="radio" class="btn-check" name="network-{server.id}" id="network-{server.id}-{name}" autocomplete="off" {checked} {disabled} onchange="setNetwork({server.id}, '{name}')">
                        <label class="btn btn-outline-primary" for="network-{server.id}-{name}">{label}</label>''')

    return f'''<tr>
        <td>{server.id}</td>
        <td><a class="btn btn-link" data-bs-toggle="collapse" href="#server-details-{server.id}" role="button" aria-expanded="false" aria-controls="server-details-{server.id}">{html.escape(server.path.name)}</a></td>
        <td>{server.port}</td>
        <td><button type="button" class="btn btn-{button_class}" id="server-{server.id}" onclick="toggleServer(event)">{button_text}</button></td>
    </tr>
    <tr id="server-details-{server.id}" class="collapse">
        <td colspan=4>
            <div class="card card-body">
                <table class="table table-striped-columns">
                    <tr><td>Listen address</td><td>{addresses}</td></tr>
                    <tr><td>Port</td><td>{server.port}</td></tr>
                    <tr><td>Status</td><td><span id="server-{server.id}-status" class="badge text-bg-{status_class}">{status_text}</span></td></tr>
                    <tr><td>Game mode</td><td>{gamemode.capitalize()}
                        <button type="button" class="btn btn-sm btn-outline-primary ms-2" onclick="setGamemode(event, {server.id}, '{other_gamemode}')">Switch to {other_gamemode}</button></td></tr>
                    <tr><td>Network</td><td><div class="btn-group btn-group-sm flex-wrap" role="group" id="network-{server.id}">
                        {"".join(network_buttons)}
                    </div></td></tr>
                </table>
                <div>
                    <button class="btn btn-sm btn-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#server-log-{server.id}" aria-expanded="false" aria-controls="server-log-{server.id}">Log</button>
                </div>
                <div class="collapse server-log mt-2" id="server-log-{server.id}" data-server-id="{server.id}">
                    <pre class="bg-body-tertiary border rounded p-2 small mb-0" style="max-height: 50vh; overflow: auto; white-space: pre-wrap;" id="server-log-{server.id}-content"></pre>
                    <form class="input-group input-group-sm mt-2" onsubmit="sendCommand(event, {server.id})">
                        <span class="input-group-text font-monospace">&gt;</span>
                        <input type="text" class="form-control font-monospace" id="server-command-{server.id}" placeholder="Console command, e.g. say hello" autocomplete="off" aria-label="Console command">
                        <button class="btn btn-outline-primary" type="submit">Send</button>
                        <div class="invalid-feedback" id="server-command-{server.id}-error"></div>
                    </form>
                </div>
            </div>
        </td>
    </tr>'''


@bottle.get('/')
def index():
    logger.debug(f"index()")

    rows = [render_server(server) for server in servers.values()]

    return f'''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Iron Golem</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI" crossorigin="anonymous"></script>
    <script src="static/iron-golem.js"></script>
</head>
<body>
    <table class="table">
        <thead>
            <tr>
                <td>#</td><td>Server</td><td>Port</td><td>Status</td>
            </tr>
        </thead>
        <tbody>
            {' '.join(rows)}
        </tbody>
    </table>
</body>
</html>'''


@bottle.get('/favicon.ico')
def favicon():
    return bottle.static_file('./favicon.ico', root=root)


@bottle.get('/static/<filepath:path>')
def static(filepath):
    return bottle.static_file(filepath, root=root)


@bottle.post('/start/<id>')
def start(id):
    logger.debug(f"start({id})")
    servers[int(id)].start()


@bottle.post('/stop/<id>')
def stop(id):
    logger.debug(f"stop({id})")
    servers[int(id)].stop()


@bottle.post('/gamemode/<id>')
def set_gamemode(id):
    gamemode = bottle.request.forms.get('gamemode')
    logger.debug(f"set_gamemode({id}, {gamemode})")
    if gamemode not in ('survival', 'creative'):
        bottle.abort(400, f"invalid game mode: {gamemode}")
    # Without force-gamemode, players who already joined keep their previous mode.
    servers[int(id)].update_config({'gamemode': gamemode, 'force-gamemode': 'true'})


@bottle.post('/network/<id>')
def set_network(id):
    network = bottle.request.forms.get('network')
    logger.debug(f"set_network({id}, {network})")
    if network not in network_labels:
        bottle.abort(400, f"invalid network: {network}")
    address = network_address(network)
    if address is None:
        bottle.abort(409, f"network {network} has no address")
    servers[int(id)].update_config({'server-ip': address})


@bottle.post('/command/<id>')
def command(id):
    command = bottle.request.forms.getunicode('command', '').strip()
    logger.info(f"command({id}, {command!r})")
    if not command or '\n' in command or '\r' in command:
        bottle.response.status = 400
        return {'error': 'Command must be a single, non-empty line'}
    if not servers[int(id)].send_command(command):
        bottle.response.status = 409
        return {'error': 'Server is not running'}
    return {}


@bottle.get('/log/<id>')
def log(id):
    """Return the log content after offset, or the tail of the log if offset is negative."""
    path = servers[int(id)].log_path
    offset = bottle.request.query.get('offset', default=-1, type=int)
    reset = offset < 0

    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return {'offset': 0, 'data': '', 'reset': True}

    if offset > size:
        # Log was truncated by a server (re)start.
        offset = 0
        reset = True

    tail = offset < 0
    if tail:
        offset = max(0, size - 16 * 1024)

    with open(path, 'rb') as f:
        f.seek(offset)
        data = f.read(1024 * 1024)

    new_offset = offset + len(data)
    if tail and offset > 0:
        # Drop the partial first line.
        data = data[data.find(b'\n') + 1:]

    return {'offset': new_offset, 'data': data.decode('utf-8', errors='replace'), 'reset': reset}


def find_server_dirs(path):
    dirs = []
    for f in path.iterdir():
        if not f.is_dir():
            continue
        if f.joinpath('server.jar').exists():
            logger.info(f"discovered server dir {f}")
            dirs.append(f)
    return dirs


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)-5s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="iron-golem")
    parser.add_argument("-a", "--address", action="store", type=str, default='localhost', help="Address to listen on")
    parser.add_argument("-p", "--port", action="store", type=int, default=10000, help="Port to listen on")
    parser.add_argument("-d", "--directory", action="store", type=str, default=".", help="Path to directory with the minecraft servers")
    parser.add_argument("--lan-interface", action="store", type=str, default=None, help="Local network interface (default: interface of the default route)")
    parser.add_argument("--vpn-interface", action="store", type=str, default="tailscale0", help="VPN interface")

    args = parser.parse_args()

    networks['lan'] = args.lan_interface or default_route_interface()
    networks['vpn'] = args.vpn_interface
    logger.info(f"local network interface: {networks['lan']}, VPN interface: {networks['vpn']}")

    server_dirs = find_server_dirs(pathlib.Path(args.directory))
    for server_dir in server_dirs:
        server = minecraft_server(server_dir, parse_config(server_dir / 'server.properties'))
        servers[server.id] = server

    bottle.run(host=args.address, port=args.port)
