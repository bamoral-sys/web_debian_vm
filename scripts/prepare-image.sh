#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_URL="https://cloud.debian.org/images/cloud/trixie/20261001-2618"
IMAGE="debian-13-genericcloud-amd64-20261001-2618.qcow2"

mkdir -p images cloud-init

if [[ ! -f keys/debian_vm_ed25519.pub ]]; then
  echo "Отсутствует SSH-ключ: keys/debian_vm_ed25519.pub" >&2
  exit 1
fi

if [[ -e images/vm.qcow2 || -e images/seed.img ]]; then
  echo "vm.qcow2 или seed.img уже существует." >&2
  exit 1
fi

rm -f "images/$IMAGE"
rm -f images/SHA512SUMS
rm -f images/selected.sha512

curl --fail --location --retry 3 \
  "$BASE_URL/$IMAGE" -o "images/$IMAGE"

curl --fail --location --retry 3 \
  "$BASE_URL/SHA512SUMS" -o images/SHA512SUMS

(
  cd images
  awk -v file="$IMAGE" \
    '$2 == file || $2 == "*" file || $2 == "./" file { print }' \
    SHA512SUMS > selected.sha512

  test -s selected.sha512
  sha512sum --check selected.sha512
)

umask 077
work_dir="$(mktemp -d images/.prepare.XXXXXX)"
trap 'rm -rf -- "$work_dir"' EXIT
ssh-keygen -q -t ed25519 -N "" -C debian-vm -f "$work_dir/host_key"

qemu-img convert -f qcow2 -O qcow2 \
  "images/$IMAGE" "$work_dir/vm.qcow2"
qemu-img resize "$work_dir/vm.qcow2" 10G
qemu-img check "$work_dir/vm.qcow2"

PUBLIC_KEY="$(cat keys/debian_vm_ed25519.pub)"

cat > "$work_dir/user-data" <<EOF
#cloud-config
hostname: debian-vm
manage_etc_hosts: true

users:
  - name: vmadmin
    shell: /bin/bash
    groups: [sudo]
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: true
    ssh_authorized_keys:
      - ${PUBLIC_KEY}

disable_root: true
ssh_pwauth: false
ssh_deletekeys: true
ssh_keys:
  ed25519_public: $(cat "$work_dir/host_key.pub")
  ed25519_private: |
$(sed 's/^/    /' "$work_dir/host_key")

package_update: true
packages:
  - openssh-server

growpart:
  mode: auto
  devices: ['/']
resize_rootfs: true

runcmd:
  - [systemctl, enable, --now, ssh]
  - [systemctl, enable, --now, serial-getty@ttyS0.service]
EOF

cat > cloud-init/meta-data <<EOF
instance-id: debian-vm-001
local-hostname: debian-vm
EOF

cat > cloud-init/network-config <<EOF
version: 2
ethernets:
  ens3:
    match:
      macaddress: "52:54:00:12:34:56"
    dhcp4: true
EOF

cloud-localds \
  --network-config=cloud-init/network-config \
  "$work_dir/seed.img" \
  "$work_dir/user-data" \
  cloud-init/meta-data

known_hosts="$(mktemp keys/.known_hosts.XXXXXX)"
printf '[127.0.0.1]:2222 %s\n' "$(cat "$work_dir/host_key.pub")" > "$known_hosts"
mv -f -- "$known_hosts" keys/known_hosts
chmod 600 "$work_dir/seed.img"
mv -- "$work_dir/seed.img" images/seed.img
mv -- "$work_dir/vm.qcow2" images/vm.qcow2

echo "Done: images/vm.qcow2 и images/seed.img"
