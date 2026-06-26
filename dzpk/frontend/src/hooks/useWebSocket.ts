import { useRef, useState, useCallback, useEffect } from 'react';
import type { ServerEvent } from '../types/game';

export function useWebSocket(
  url: string,
  onMessage: (evt: ServerEvent) => void,
) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const maxReconnect = 5;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  const pendingRef = useRef<string[]>([]);

  onMessageRef.current = onMessage;

  const send = useCallback((msg: object) => {
    const data = JSON.stringify(msg);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    } else {
      pendingRef.current.push(data);
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setConnected(true);
        reconnectCountRef.current = 0;
        // 发送认证消息（如果有 token）
        const token = localStorage.getItem('dzpk_token');
        if (token) {
          ws.send(JSON.stringify({ action: 'auth', data: { token } }));
        }
        // 然后发送缓冲的待发消息
        for (const msg of pendingRef.current) {
          ws.send(msg);
        }
        pendingRef.current = [];
      };

      ws.onmessage = (event) => {
        try {
          const parsed: ServerEvent = JSON.parse(event.data);
          onMessageRef.current(parsed);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (reconnectCountRef.current < maxReconnect) {
          reconnectCountRef.current += 1;
          timerRef.current = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      setConnected(false);
    }
  }, [url]);

  const disconnect = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    reconnectCountRef.current = maxReconnect; // prevent auto reconnect
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, send, disconnect, connect };
}
