#!/usr/bin/env bash
set -euo pipefail

exec qemu-system-x86_64 \
  -machine accel=tcg \
  -m 2048 \
  -smp 2 \
  -drive file=images/vm.qcow2,format=qcow2,if=virtio \
  -drive file=images/seed.img,format=raw,if=virtio,readonly=on \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 \
  -device virtio-net-pci,netdev=net0,mac=52:54:00:12:34:56 \
  -chardev socket,id=serial0,path=/tmp/debian-vm-serial.sock,server=on,wait=off \
  -serial chardev:serial0 \
  -qmp unix:/tmp/debian-vm-qmp.sock,server=on,wait=off
