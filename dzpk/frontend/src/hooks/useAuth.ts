import { useState, useCallback, useRef, useEffect } from 'react';
import type { UserInfo } from '../types/auth';

const TOKEN_KEY = 'dzpk_token';
const DEVICE_ID_KEY = 'dzpk_deviceId';

function generateDeviceId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = generateDeviceId();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

function normalizeUser(raw: any): UserInfo {
  return {
    id: raw.id,
    username: raw.username ?? null,
    chips: raw.chips ?? 0,
    isAnonymous: raw.is_anonymous ?? raw.isAnonymous ?? false,
    totalHands: raw.total_hands ?? raw.totalHands ?? 0,
    totalWins: raw.total_wins ?? raw.totalWins ?? 0,
    totalProfit: raw.total_profit ?? raw.totalProfit ?? 0,
    createdAt: raw.created_at ?? raw.createdAt ?? '',
    lastLoginAt: raw.last_login_at ?? raw.lastLoginAt ?? '',
  };
}

async function apiCall(path: string, options: RequestInit = {}): Promise<any> {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(true);
  const initializedRef = useRef(false);

  const saveToken = useCallback((t: string) => {
    localStorage.setItem(TOKEN_KEY, t);
    setToken(t);
  }, []);

  const initGuest = useCallback(async () => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const savedToken = localStorage.getItem(TOKEN_KEY);

    try {
      // 如果已有 token，尝试获取用户信息
      if (savedToken) {
        const data = await apiCall('/api/auth/me');
        setUser(normalizeUser(data));
        setToken(savedToken);
        setLoading(false);
        return;
      }
    } catch {
      // token 无效，清除并重新创建匿名账号
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    }

    try {
      const deviceId = getDeviceId();
      const data = await apiCall('/api/auth/guest', {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId }),
      });
      saveToken(data.token);
      localStorage.setItem('dzpk_userId', data.user_id);
      setUser({ id: data.user_id, username: null, chips: data.chips, isAnonymous: true, totalHands: 0, totalWins: 0, totalProfit: 0, createdAt: '', lastLoginAt: '' });
    } catch (e) {
      console.error('初始化匿名账号失败:', e);
    } finally {
      setLoading(false);
    }
  }, [saveToken]);

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiCall('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    saveToken(data.token);
    localStorage.setItem('dzpk_userId', data.user.id);
    const u = normalizeUser(data.user);
    setUser(u);
    return u;
  }, [saveToken]);

  const upgrade = useCallback(async (username: string, password: string) => {
    const data = await apiCall('/api/auth/upgrade', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    saveToken(data.token);
    localStorage.setItem('dzpk_userId', data.user.id);
    const u = normalizeUser(data.user);
    setUser(u);
    return u;
  }, [saveToken]);

  const getMe = useCallback(async () => {
    const data = await apiCall('/api/auth/me');
    const u = normalizeUser(data);
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(async () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('dzpk_userId');
    setToken(null);
    setUser(null);
    setLoading(true);
    try {
      const deviceId = getDeviceId();
      const data = await apiCall('/api/auth/guest', {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId }),
      });
      localStorage.setItem(TOKEN_KEY, data.token);
      localStorage.setItem('dzpk_userId', data.user_id);
      setToken(data.token);
      setUser({ id: data.user_id, username: null, chips: data.chips, isAnonymous: true, totalHands: 0, totalWins: 0, totalProfit: 0, createdAt: '', lastLoginAt: '' });
    } catch (e) {
      console.error('退出后重建匿名账号失败:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    initGuest();
  }, [initGuest]);

  return { user, token, loading, initGuest, login, upgrade, getMe, logout };
}
