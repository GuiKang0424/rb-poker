import { useState } from 'react';

interface Props {
  isAnonymous: boolean;
  onLogin: (username: string, password: string) => Promise<unknown>;
  onUpgrade: (username: string, password: string) => Promise<unknown>;
  onClose: () => void;
}

export function Login({ isAnonymous, onLogin, onUpgrade, onClose }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>(isAnonymous ? 'register' : 'login');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setError('');
    if (!username.trim()) { setError('请输入用户名'); return; }
    if (username.trim().length < 3) { setError('用户名至少 3 个字符'); return; }
    if (password.length < 6) { setError('密码至少 6 位'); return; }

    setSubmitting(true);
    try {
      if (mode === 'register') {
        await onUpgrade(username.trim(), password);
      } else {
        await onLogin(username.trim(), password);
      }
      onClose();
    } catch (e: any) {
      setError(e.message || '操作失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-xl p-6 w-80 shadow-2xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold">
            {mode === 'login' ? '登录' : '注册账号'}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-lg leading-none"
          >
            ×
          </button>
        </div>

        {isAnonymous && mode === 'register' && (
          <div className="mb-3 p-2 bg-blue-600/20 border border-blue-600/40 rounded text-xs text-blue-300">
            注册后你的筹码和战绩将绑定到账号，可在其他设备登录
          </div>
        )}

        <div className="space-y-3 mb-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => { setUsername(e.target.value); setError(''); }}
              placeholder="3-20 个字符"
              maxLength={20}
              className="w-full px-3 py-2 bg-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(''); }}
              placeholder="至少 6 位"
              maxLength={64}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              className="w-full px-3 py-2 bg-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white text-sm"
            />
          </div>
        </div>

        {error && (
          <div className="mb-3 p-2 bg-red-600/20 border border-red-600/40 rounded text-xs text-red-400">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 rounded-lg font-medium text-sm transition-colors mb-3"
        >
          {submitting ? '处理中...' : mode === 'login' ? '登录' : '注册'}
        </button>

        <div className="text-center">
          <button
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
            className="text-xs text-slate-400 hover:text-blue-400 transition-colors"
          >
            {mode === 'login' ? '没有账号？注册' : '已有账号？登录'}
          </button>
        </div>
      </div>
    </div>
  );
}
