'use client';

import { useEffect, useState, useRef } from 'react';

type VmStatus = {
  process_running: boolean;
};

const API_URL = 'http://127.0.0.1:8000';
const WEBSOCKET_URL = 'ws://127.0.0.1:8000';

export function VmTerminal() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | undefined;

    async function connect() {
      const { Terminal } = await import('@xterm/xterm');

      if (disposed || !containerRef.current) {
        return;
      }

      const terminal = new Terminal({
        cols: 80,
        rows: 24,
        cursorBlink: true,
        fontSize: 14,
        theme: {
          background: '#0f172a',
          foreground: '#e2e8f0',
        },
      });

      terminal.open(containerRef.current);

      let socket: WebSocket | null = null;
      let retryTimer: ReturnType<typeof setTimeout> | undefined;
      const encoder = new TextEncoder();

      function connectSocket() {
        if (disposed) return;

        terminal.writeln('\r\nПодключение к SSH…');

        const connection = new WebSocket(`${WEBSOCKET_URL}/api/vm/ssh`);
        socket = connection;
        connection.binaryType = 'arraybuffer';

        connection.onopen = () => {
          if (!disposed) {
            terminal.focus();
          }
        };

        connection.onmessage = (event) => {
          if (disposed) return;

          if (event.data instanceof ArrayBuffer) {
            terminal.write(new Uint8Array(event.data));
          }
        };

        // После ошибки WebSocket вызывает onclose: повтор планируем только там.
        connection.onclose = (event) => {
          if (disposed) return;

          if (event.code === 1000 || event.code === 1008) {
            terminal.writeln(
              `\r\nСоединение закрыто: ${event.reason || event.code}`
            );
            return;
          }

          terminal.writeln(
            '\r\nSSH недоступен. Повторная попытка через 3 секунды…'
          );
          retryTimer = setTimeout(connectSocket, 3000);
        };
      }

      const inputSubscription = terminal.onData((data) => {
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(encoder.encode(data));
        }
      });

      cleanup = () => {
        clearTimeout(retryTimer);
        inputSubscription.dispose();
        socket?.close();
        terminal.dispose();
      };

      connectSocket();
    }

    void connect().catch((error) => {
      console.error('Не удалось создать терминал:', error);
    });

    return () => {
      disposed = true;
      cleanup?.();
    };
  }, []);

  return (
    <div className="vm-terminal">
      <div ref={containerRef} />
    </div>
  );
}


async function getVmStatus(): Promise<VmStatus> {
  const response = await fetch(
    `${API_URL}/api/vm/status`,
     {cache: 'no-store',}
  );

  if (!response.ok) {
    throw new Error(`Ошибка получения статуса: ${response.status}`);
  }

  return response.json();
}

export default function Home() {
  const [vm, setVm] = useState<VmStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);


  async function handleStart() {
    setIsStarting(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/vm/start`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Ошибка запуска: ${response.status}`);
      }

      await refreshStatus();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : 'Ошибка запроса'
      );
    } finally {
      setIsStarting(false);
    }
  }

  async function handleReset(){
    setIsStarting(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/vm/reset`,{
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Ошибка перезапуска: ${response.status}`);
      }

      await refreshStatus();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : 'Ошибка перезапуска'
      );
    } finally {
      setIsStarting(false);
    }
  }

  async function handlePowerOff(){
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/vm/powerdown`,{
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Ошибка выключения: ${response.status}`);
      }

      await refreshStatus();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : 'Ошибка выключения'
      );
    }
  }

  async function refreshStatus() {
    try {
      const data = await getVmStatus();

      setVm(data);
      setError(null);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : 'Ошибка запроса'
      );
    }
  }

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    async function pollStatus() {
      try {
        const data = await getVmStatus();

        if (!stopped) {
          setVm(data);
          setError(null);
        }
      } catch {
        if (!stopped) {
          setError('Не удалось обновить статус');
        }
      } finally {
        if (!stopped) {
          timer = setTimeout(pollStatus, 3000);
        }
      }
    }

    void pollStatus();

    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, []);

  return (
    <main className="dashboard">
      <h1>Управление виртуальной машиной</h1>

      <p>
        Состояние:{' '}
        {vm === null
          ? 'неизвестно'
          : vm.process_running
            ? 'процесс ВМ запущен'
            : 'процесс ВМ остановлен'}
      </p>

      <div className="vm-actions">
        <button className="vm-button-primary" onClick={handleStart}>
          Запустить
        </button>

        <button onClick={refreshStatus}>
          Обновить статус
        </button>

        <button onClick={handleReset}>
          Перезапустить
        </button>

        <button className="vm-button-danger" onClick={handlePowerOff}>
          Выключить
        </button>
      </div>
    {vm?.process_running && <VmTerminal />}
    </main>
  );
}
