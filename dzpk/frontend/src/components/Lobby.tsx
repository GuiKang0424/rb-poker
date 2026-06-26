import { useState, useEffect, useCallback } from 'react';
import { useGameContext } from '../context/GameContext';
import { useAuth } from '../hooks/useAuth';
import { UserProfile } from './UserProfile';
import { Login } from './Login';

interface RoomItem {
  roomId: string;
  playerCount: number;
  maxPlayers: number;
  smallBlind: number;
  bigBlind: number;
}

export function Lobby() {
  const { dispatch, joinRoom, setPage } = useGameContext();
  const { user, loading: authLoading, login, upgrade, logout } = useAuth();
  const [nickname, setNickname] = useState(() => localStorage.getItem('dzpk_nickname') || '');
  const [roomIdInput, setRoomIdInput] = useState('');
  const [rooms, setRooms] = useState<RoomItem[]>([]);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [showLogin, setShowLogin] = useState(false);

  const fetchRooms = useCallback(async () => {
    try {
      const res = await fetch('/api/rooms');
      const data = await res.json();
      setRooms(data || []);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchRooms();
    const interval = setInterval(fetchRooms, 5000);
    return () => clearInterval(interval);
  }, [fetchRooms]);

  const validateNickname = () => {
    if (!nickname.trim()) {
      setError('请输入昵称');
      return false;
    }
    localStorage.setItem('dzpk_nickname', nickname.trim());
    return true;
  };

  const handleCreateRoom = async () => {
    if (!validateNickname()) return;
    setCreating(true);
    setError('');
    try {
      const userId = localStorage.getItem('dzpk_userId') || crypto.randomUUID();
      const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nickname: nickname.trim(),
          userId,
          small_blind: 5,
          big_blind: 10,
          max_players: 9,
        }),
      });
      const data = await res.json();
      if (data.room_id) {
        dispatch({ type: 'SET_ROOM', roomId: data.room_id });
        joinRoom(data.room_id, nickname.trim());
        setPage('game');
      } else {
        setError('创建房间失败');
      }
    } catch {
      setError('创建房间失败');
    } finally {
      setCreating(false);
    }
  };

  const handleJoinRoom = (roomId: string) => {
    if (!validateNickname()) return;
    dispatch({ type: 'SET_ROOM', roomId });
    joinRoom(roomId, nickname.trim());
    setPage('game');
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      {/* 用户信息栏 */}
      <div className="w-full max-w-md mb-4 flex justify-center">
        <UserProfile
          user={user}
          loading={authLoading}
          onLoginClick={() => setShowLogin(true)}
          onLogout={logout}
        />
      </div>

      <div className="bg-slate-800 rounded-2xl p-8 w-full max-w-md shadow-xl"
      >
        <h1 className="text-3xl font-bold text-center mb-8"
        >德州扑克</h1>

        {/* Nickname */}
        <div className="mb-6"
        >
          <label className="block text-sm text-slate-400 mb-2"
          >昵称</label>
          <input
            type="text"
            value={nickname}
            onChange={(e) => { setNickname(e.target.value); setError(''); }}
            placeholder="输入你的昵称"
            className="w-full px-4 py-3 bg-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
          />
        </div>

        {/* Create room */}
        <button
          onClick={handleCreateRoom}
          disabled={creating}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 rounded-lg font-bold text-lg mb-4 transition-colors"
        >
          {creating ? '创建中...' : '创建房间'}
        </button>

        {/* Join by ID */}
        <div className="flex gap-2 mb-6"
        >
          <input
            type="text"
            value={roomIdInput}
            onChange={(e) => { setRoomIdInput(e.target.value); setError(''); }}
            placeholder="输入房间号加入"
            className="flex-1 px-4 py-3 bg-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
          />
          <button
            onClick={() => handleJoinRoom(roomIdInput.trim())}
            disabled={!roomIdInput.trim()}
            className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-slate-600 rounded-lg font-medium transition-colors"
          >
            加入
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-600/20 border border-red-600 rounded-lg text-red-400 text-sm"
          >{error}</div>
        )}

        {/* Room list */}
        <div className="border-t border-slate-700 pt-4"
        >
          <h2 className="text-lg font-semibold mb-3"
          >房间列表</h2>
          {rooms.length === 0 ? (
            <p className="text-slate-500 text-sm"
            >暂无房间</p>
          ) : (
            <div className="space-y-2"
            >
              {rooms.map((room) => (
                <button
                  key={room.roomId}
                  onClick={() => handleJoinRoom(room.roomId)}
                  className="w-full text-left p-3 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                >
                  <div className="flex justify-between items-center"
                  >
                    <span className="font-medium"
                    >房间 {room.roomId}</span>
                    <span className="text-sm text-slate-400"
                    >
                      {room.playerCount}/{room.maxPlayers} 人
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mt-1"
                  >
                    盲注: {room.smallBlind}/{room.bigBlind}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 登录/注册弹窗 */}
      {showLogin && (
        <Login
          isAnonymous={user?.isAnonymous ?? true}
          onLogin={login}
          onUpgrade={upgrade}
          onClose={() => setShowLogin(false)}
        />
      )}
    </div>
  );
}
