#!/usr/bin/env bash
#
# Install iron-golem as a systemd user service, running from a python venv.
#
# Usage: ./install.sh [iron-golem arguments...]
#   e.g. ./install.sh --address 0.0.0.0 --directory ~/minecraft
#
# The arguments are baked into the service; re-run the script to change them.

set -euo pipefail

src_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
venv_dir="$src_dir/.venv"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit_file="$unit_dir/iron-golem.service"

usage() {
    cat <<EOF
Usage: $0 [iron-golem arguments...]

Install iron-golem as a systemd user service, running from a python venv
in $venv_dir.

All arguments are passed to iron-golem and baked into the service;
re-run the script to change them. Relative paths are resolved against
the current directory.

  e.g. $0 --address 0.0.0.0 --directory ~/minecraft

Options:
  -h, --help  Show this help and exit, without installing anything
EOF
    # The venv may be missing or incomplete (e.g. an interrupted install).
    local golem_help
    if golem_help=$("$venv_dir/bin/python" "$src_dir/iron-golem.py" --help 2>/dev/null); then
        echo
        echo "iron-golem arguments:"
        sed -n '/^options:/,$p' <<< "$golem_help"
    else
        echo
        echo "See iron-golem.py --help for the available iron-golem arguments."
    fi
}

for arg in "$@"; do
    case "$arg" in
        -h|--help) usage; exit 0 ;;
    esac
done

if ! command -v java > /dev/null; then
    echo "warning: java not found, minecraft servers won't be able to start" >&2
fi

echo "Setting up venv in $venv_dir"
python3 -m venv "$venv_dir"
"$venv_dir/bin/pip" install --quiet --upgrade -r "$src_dir/requirements.txt"

# Resolve relative paths (e.g. --directory) against the current directory,
# not the service's working directory.
args=()
for arg in "$@"; do
    if [[ -e "$arg" ]]; then
        arg=$(realpath "$arg")
    fi
    args+=("$(printf '%q' "$arg")")
done

echo "Writing $unit_file"
mkdir -p "$unit_dir"
cat > "$unit_file" <<UNIT
[Unit]
Description=Iron Golem minecraft server supervisor
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$src_dir
ExecStart=$venv_dir/bin/python $src_dir/iron-golem.py ${args[*]}
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
# Minecraft servers are in the same cgroup and get SIGTERM on stop too,
# give them time to save their worlds.
TimeoutStopSec=90

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable iron-golem.service
systemctl --user restart iron-golem.service

# Without lingering, user services only run while the user is logged in.
if [[ "$(loginctl show-user "$USER" --property=Linger --value 2>/dev/null)" != "yes" ]]; then
    echo "Enabling lingering for $USER, so the service starts at boot"
    loginctl enable-linger "$USER"
fi

echo "Done. Status: systemctl --user status iron-golem, logs: journalctl --user -u iron-golem -f"
