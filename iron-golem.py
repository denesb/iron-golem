#!/usr/bin/env python3

import argparse
import bottle
import logging
import pathlib
import subprocess


logger = logging.getLogger('iron-golem')

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
        self.path = path
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
        self._process = subprocess.Popen(args, stdout=self._logfile, stderr=self._logfile, text=True)

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


@bottle.route('/')
def index():
    logger.debug(f"index()")

    rows = []

    for server in servers.values():
        rows.append(f'<tr><td>{server.path}</td><td>{server.ip}:{server.port}</td></tr>')

    return f"""<html>
<head>
    <title>Iron Golem</title>
</head>
<body>
    <table>
        <thead>
            <tr>
                <td>Server</td><td>Address:Port</td>
            </tr>
        </thead>
        <tbody>
            {' '.join(rows)}
        </tbody>
    </table>
</body>
</html>"""


@bottle.route('/start/<id>')
def start(id):
    logger.debug(f"start({id})")
    servers[int(id)].start()


@bottle.route('/stop/<id>')
def start(id):
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
