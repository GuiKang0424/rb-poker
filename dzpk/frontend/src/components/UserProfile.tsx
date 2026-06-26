import { useState } from 'react';
import type { UserInfo } from '../types/auth';

interface Props {
  user: UserInfo | null;
  loading: boolean;
  onLoginClick: () => void;
  onLogout: () => void;
}

function formatDate(s: string): string {
  if (!s) return '-';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString('zh-CN', { hour12: false });
}

export function UserProfile({ user, loading, onLoginClick, onLogout }: Props) {
  const [showDetail, setShowDetail] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <div className="w-6 h-6 rounded-full bg-slate-600 animate-pulse" />
        <span>加载中...</span>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const displayName = user.username || '游客';

  return (
    <>
      <div className="flex items-center gap-3">
        {/* 用户信息（可点击展开） */}
        <button
          onClick={() => setShowDetail(true)}
          className="flex items-center gap-3 hover:bg-slate-700/50 rounded px-2 py-1 transition-colors"
        >
          <div className="text-right">
            <div className="text-sm font-medium text-white">
              {displayName}
              {user.isAnonymous && (
                <span className="ml-1 text-xs text-slate-400">(匿名)</span>
              )}
            </div>
            <div className="text-xs text-yellow-400">
              筹码: {user.chips.toLocaleString()}
            </div>
          </div>

          <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center text-sm font-bold text-slate-300">
            {displayName[0].toUpperCase()}
          </div>
        </button>

        {/* 操作按钮 */}
        {user.isAnonymous ? (
          <button
            onClick={onLoginClick}
            className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 rounded transition-colors"
          >
            注册/登录
          </button>
        ) : (
          <button
            onClick={onLogout}
            className="px-3 py-1 text-xs bg-slate-600 hover:bg-slate-500 rounded transition-colors"
          >
            退出
          </button>
        )}
      </div>

      {/* 详情弹窗 */}
      {showDetail && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setShowDetail(false)}
        >
          <div
            className="bg-slate-800 rounded-2xl p-6 w-full max-w-sm shadow-xl mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-4 mb-6">
              <div className="w-14 h-14 rounded-full bg-slate-600 flex items-center justify-center text-2xl font-bold text-slate-200">
                {displayName[0].toUpperCase()}
              </div>
              <div>
                <div className="text-lg font-semibold text-white">
                  {displayName}
                  {user.isAnonymous && (
                    <span className="ml-2 text-xs text-slate-400">(匿名)</span>
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-1 break-all">
                  ID: {user.id}
                </div>
              </div>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-slate-700 pb-2">
                <span className="text-slate-400">筹码余额</span>
                <span className="text-yellow-400 font-semibold">
                  {user.chips.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between border-b border-slate-700 pb-2">
                <span className="text-slate-400">总手数</span>
                <span className="text-white">{user.totalHands}</span>
              </div>
              <div className="flex justify-between border-b border-slate-700 pb-2">
                <span className="text-slate-400">胜场数</span>
                <span className="text-white">{user.totalWins}</span>
              </div>
              <div className="flex justify-between border-b border-slate-700 pb-2">
                <span className="text-slate-400">总盈利</span>
                <span
                  className={
                    user.totalProfit > 0
                      ? 'text-green-400'
                      : user.totalProfit < 0
                        ? 'text-red-400'
                        : 'text-white'
                  }
                >
                  {user.totalProfit > 0 ? '+' : ''}
                  {user.totalProfit.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between border-b border-slate-700 pb-2">
                <span className="text-slate-400">注册时间</span>
                <span className="text-white text-xs">{formatDate(user.createdAt)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">最近登录</span>
                <span className="text-white text-xs">{formatDate(user.lastLoginAt)}</span>
              </div>
            </div>

            <button
              onClick={() => setShowDetail(false)}
              className="mt-6 w-full py-2 bg-slate-700 hover:bg-slate-600 rounded transition-colors text-sm"
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </>
  );
}
