#!/usr/bin/env python3

import argparse
import bottle
import logging
import pathlib
import subprocess


logger = logging.getLogger('iron-golem')

root = pathlib.Path(__file__).resolve().parent

servers = {}
last_id = 0


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
    def port(self):
        return int(self.config['server-port'])

    def start(self):
        self._logfile = open(self.path / 'server.log', 'w')
        args = [
            '/usr/bin/java',
            '-Xmx1024M',
            '-Xms1024M',
            '-jar',
            str(self.path.joinpath('server.jar')),
            'nogui',
        ]
        self._process = subprocess.Popen(args, stdout=self._logfile, stderr=self._logfile, cwd=self.path, text=True)

    def stop(self):
        self._process.terminate()



def parse_config(config_file):
    config = {}
    with open (config_file, 'r') as f:
        for l in f:
            l = l.strip()

            if not l:
                continue
            if l[0] == '#':
                continue

            key, value = l.split('=')

            key = key.replace('"', '')

            config[key] = value.replace('"', '')

    return config


@bottle.get('/')
def index():
    logger.debug(f"index()")

    rows = []

    for server in servers.values():
        rows.append(f'<tr><td>{server.id}</td><td>{server.path.name}</td><td>{server.ip}:{server.port}</td></tr>')

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Iron Golem</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI" crossorigin="anonymous"></script>
</head>
<body>
    <table class="table">
        <thead>
            <tr>
                <td>Id</td><td>Server</td><td>Address:Port</td>
            </tr>
        </thead>
        <tbody>
            {' '.join(rows)}
        </tbody>
    </table>
</body>
</html>"""


@bottle.get('/favicon.ico')
def favicon():
    return bottle.static_file('./favicon.ico', root=root)


@bottle.post('/start/<id>')
def start(id):
    logger.debug(f"start({id})")
    servers[int(id)].start()


@bottle.post('/stop/<id>')
def stop(id):
    logger.debug(f"stop({id})")
    servers[int(id)].stop()


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

    args = parser.parse_args()

    server_dirs = find_server_dirs(pathlib.Path(args.directory))
    for server_dir in server_dirs:
        server = minecraft_server(server_dir, parse_config(server_dir / 'server.properties'))
        servers[server.id] = server

    bottle.run(host=args.address, port=args.port)
