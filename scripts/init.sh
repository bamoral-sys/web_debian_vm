#!/usr/bin/env bash
set -euo pipefail

cd /workspace

KEY_DIR="keys"
PRIVATE_KEY="$KEY_DIR/debian_vm_ed25519"
PUBLIC_KEY="${PRIVATE_KEY}.pub"

mkdir -p "$KEY_DIR" images cloud-init back/logs

echo "[INIT] Checking SSH keys..."

if [[ ! -f "$PRIVATE_KEY" ]]; then
    if [[ -e "$PUBLIC_KEY" || -e images/vm.qcow2 || -e images/seed.img ]]; then
        echo "[ERROR] SSH private key is missing for existing VM assets."
        echo "Restore the original client key before continuing."
        exit 1
    fi

    ssh-keygen -t ed25519 \
        -f "$PRIVATE_KEY" \
        -N "" \
        -C "vmadmin"

    echo "[INIT] SSH keys generated."
else
    chmod 600 "$PRIVATE_KEY"
    derived_key="$(ssh-keygen -y -f "$PRIVATE_KEY" | awk '{print $1, $2}')"
    if [[ ! -f "$PUBLIC_KEY" ]]; then
        printf '%s\n' "$derived_key" > "$PUBLIC_KEY"
        echo "[INIT] Public key restored."
    elif [[ "$(awk 'NR == 1 {print $1, $2}' "$PUBLIC_KEY")" != "$derived_key" ]]; then
        echo "[ERROR] Client SSH public and private keys do not match." >&2
        exit 1
    fi

    echo "[INIT] Existing SSH key reused."
fi

chmod 644 "$PUBLIC_KEY"

echo "[INIT] Checking Debian image..."

if [[ -f images/vm.qcow2 && -f images/seed.img ]]; then
    echo "[INIT] Debian image already exists."
    if ! ssh-keygen -F '[127.0.0.1]:2222' -f "$KEY_DIR/known_hosts" >/dev/null 2>&1; then
        echo "[INIT] Existing VM has no trusted SSH host key. See README.md." >&2
    fi
elif [[ ! -e images/vm.qcow2 && ! -e images/seed.img ]]; then
    echo "[INIT] Preparing Debian 13 image..."
    bash scripts/prepare-image.sh
else
    echo "[ERROR] Incomplete image state."
    echo "Check images/vm.qcow2 and images/seed.img."
    exit 1
fi

echo "[INIT] Initialization completed successfully."
