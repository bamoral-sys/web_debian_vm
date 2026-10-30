## 1. Подготовьте программы

Нужны установленный и запущенный Docker Engine, Git и инструменты подготовки образа:

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates qemu-utils cloud-image-utils openssh-client
```

## 2. Склонируйте репозиторий

```bash
git clone https://github.com/bamoral-sys/web_debian_vm.git
cd web_debian_vm
```

## 3. Создайте SSH-ключ

```bash
mkdir -p keys back/logs

if [ ! -f keys/debian_vm_ed25519 ]; then
  ssh-keygen -t ed25519 -N "" -f keys/debian_vm_ed25519 -C vmadmin
fi

chmod 600 keys/debian_vm_ed25519
touch keys/known_hosts
```

## 4. Подготовьте диск Debian

```bash
bash scripts/prepare-image.sh
```

## 5. Соберите Docker-образы

```bash
docker build -f Dockerfile.backend -t debian-vm-backend .

docker build \
  -f frontend/web_debian_vm/Dockerfile.frontend \
  -t debian-vm-frontend \
  frontend/web_debian_vm
```

## 6. Запустите backend

```bash
docker run -d --rm --init \
  --name debian-vm-backend \
  -p 127.0.0.1:8000:8000 \
  --mount "type=bind,source=$(pwd)/images,target=/app/images" \
  --mount "type=bind,source=$(pwd)/back/logs,target=/app/back/logs" \
  --mount "type=bind,source=$(pwd)/keys,target=/run/ssh,readonly" \
  -e VM_SSH_KEY=/run/ssh/debian_vm_ed25519 \
  -e VM_KNOWN_HOSTS=/run/ssh/known_hosts \
  debian-vm-backend
```

## 7. Запустите frontend

```bash
docker run -d --rm --init \
  --name debian-vm-frontend \
  -p 127.0.0.1:3000:3000 \
  debian-vm-frontend
```

фронтенд будет доступен по адресу [http://localhost:3000](http://localhost:3000)

## P.S.
Если в терминале вечно идёт подключение к ssh дольше минуты, то попробуйте добавить ключ в known_hosts
```bash
host_key=$(docker exec debian-vm-backend python -c \
"import asyncio, asyncssh; key = asyncio.run(asyncio.wait_for(asyncssh.get_server_host_key('127.0.0.1', port=2222, server_host_key_algs=['ssh-ed25519']), timeout=15)); print('[127.0.0.1]:2222 ' + key.export_public_key().decode().strip())") \
  && printf '%s\n' "$host_key" > keys/known_hosts
  ```