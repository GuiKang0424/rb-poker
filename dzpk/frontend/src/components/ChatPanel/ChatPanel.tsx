import { useState, useRef, useEffect, useCallback } from 'react';
import { useGameContext } from '../../context/GameContext';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { QuickPhrases } from './QuickPhrases';

export function ChatPanel() {
  const { state, sendChat } = useGameContext();
  const [collapsed, setCollapsed] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasNewRef = useRef(false);

  const messages = state.messages;
  const myUserId = state.mySeat !== null && state.players[state.mySeat]
    ? state.players[state.mySeat].nickname
    : '';

  // 自动滚动到底部
  useEffect(() => {
    if (!collapsed) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      hasNewRef.current = false;
    } else {
      hasNewRef.current = true;
    }
  }, [messages, collapsed]);

  const handleSendText = useCallback(
    (text: string) => {
      sendChat('text', text);
    },
    [sendChat],
  );

  const handleSendQuick = useCallback(
    (phraseId: number) => {
      sendChat('quick', undefined, phraseId);
    },
    [sendChat],
  );

  // 判断消息是否为当前玩家发送（用于左右对齐）
  // 系统消息没有 userId，不是"我的"
  // 等待区玩家通过 nickname 匹配（因为我的 seat 为 null）
  const isMyMessage = useCallback(
    (msg: { seat: number; nickname: string; type: string }) => {
      if (msg.type === 'system') return false;
      if (state.mySeat !== null) {
        return msg.seat === state.mySeat;
      }
      // 等待区玩家：通过昵称匹配
      return msg.nickname === myUserId || msg.seat === -1;
    },
    [state.mySeat, myUserId],
  );

  return (
    <div className={`flex flex-col bg-slate-800/50 border-l border-slate-700 transition-all ${collapsed ? 'w-10' : 'w-72'}`}>
      {/* 折叠/展开按钮 */}
      <button
        onClick={() => {
          setCollapsed(!collapsed);
          if (collapsed) hasNewRef.current = false;
        }}
        className="flex items-center justify-between px-3 py-2 border-b border-slate-700 hover:bg-slate-700/50 transition-colors"
        title={collapsed ? '展开聊天' : '收起聊天'}
      >
        {collapsed ? (
          <span className="text-sm text-slate-400 relative">
            💬
            {hasNewRef.current && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full" />
            )}
          </span>
        ) : (
          <>
            <span className="text-sm font-semibold text-slate-400">聊天</span>
            <span className="text-xs text-slate-600">收起</span>
          </>
        )}
      </button>

      {!collapsed && (
        <>
          {/* 消息列表 */}
          <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
            {messages.length === 0 && (
              <p className="text-xs text-slate-600 text-center py-4">
                暂无消息，来打个招呼吧
              </p>
            )}
            {messages.map((msg, i) => (
              <ChatMessage
                key={`${msg.timestamp}-${i}`}
                message={msg}
                isMyMessage={isMyMessage(msg)}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* 快捷短语 */}
          <div className="px-2 py-1.5 border-t border-slate-700/50">
            <QuickPhrases onSend={handleSendQuick} />
          </div>

          {/* 输入框 */}
          <div className="px-2 pb-2">
            <ChatInput onSend={handleSendText} />
          </div>
        </>
      )}
    </div>
  );
}
