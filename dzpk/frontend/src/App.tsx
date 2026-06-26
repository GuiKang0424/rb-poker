import { useEffect, useCallback, useRef } from 'react';
import { useGameContext } from './context/GameContext';
import { useWebSocket } from './hooks/useWebSocket';
import { useAuth } from './hooks/useAuth';
import { Lobby } from './components/Lobby';
import { GameTable } from './components/GameTable';
import type { ServerEvent } from './types/game';

export default function App() {
  const { state, dispatch, sendRef, page } = useGameContext();
  const { initGuest } = useAuth();

  // 应用启动时自动初始化匿名账号
  useEffect(() => {
    initGuest();
  }, [initGuest]);

  const onMessage = useCallback(
    (evt: ServerEvent) => {
      dispatch({ type: 'SERVER_EVENT', event: evt });
    },
    [dispatch],
  );

  const wsUrl = state.roomId
    ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/${state.roomId}`
    : '';

  const { send, connected, connect, disconnect } = useWebSocket(wsUrl, onMessage);
  const prevRoomRef = useRef<string | null>(null);

  useEffect(() => {
    sendRef.current = send;
  }, [sendRef, send]);

  useEffect(() => {
    if (state.roomId && state.roomId !== prevRoomRef.current) {
      prevRoomRef.current = state.roomId;
      setTimeout(() => connect(), 100);
    }
    if (!state.roomId && prevRoomRef.current) {
      prevRoomRef.current = null;
      disconnect();
    }
  }, [state.roomId, connect, disconnect]);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {page === 'lobby' && <Lobby />}
      {page === 'game' && (
        <>
          <GameTable />
          {!connected && state.roomId && (
            <div className="fixed top-4 right-4 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm">
              连接断开...
            </div>
          )}
        </>
      )}
    </div>
  );
}
