import type { ChatMessage as ChatMessageType } from '../../types/game';

interface Props {
  message: ChatMessageType;
  isMyMessage: boolean;
}

/** 快捷短语本地映射表 */
const QUICK_PHRASES: Record<number, string> = {
  0: '好牌！',
  1: '运气不错 🍀',
  2: 'All-in 了！',
  3: '这把我弃了',
  4: '跟一手',
  5: '加注！',
  6: 'GG 👍',
  7: '打得漂亮',
};

export const QUICK_PHRASE_LIST = Object.entries(QUICK_PHRASES).map(([id, text]) => ({
  id: parseInt(id),
  text,
}));

export function ChatMessage({ message, isMyMessage }: Props) {
  // 系统消息
  if (message.type === 'system') {
    return (
      <div className="flex justify-center py-1">
        <span className="text-xs text-slate-500 italic">
          —— {message.content} ——
        </span>
      </div>
    );
  }

  // 快捷短语：用 phrase_id 查表渲染
  let content = message.content;
  if (message.type === 'quick') {
    const phraseId = parseInt(message.content);
    content = QUICK_PHRASES[phraseId] || message.content;
  }

  // 自己的消息右对齐，别人的左对齐
  const isMine = isMyMessage;

  return (
    <div className={`flex ${isMine ? 'justify-end' : 'justify-start'} py-0.5`}>
      <div className={`max-w-[85%] ${isMine ? 'order-1' : ''}`}>
        {!isMine && (
          <span className="text-xs text-slate-400 ml-1 block">
            {message.nickname}
          </span>
        )}
        <div
          className={`px-2.5 py-1 rounded-lg text-sm break-words ${
            isMine
              ? 'bg-blue-600 text-white rounded-br-sm'
              : 'bg-slate-700 text-slate-200 rounded-bl-sm'
          }`}
        >
          {content}
        </div>
        <span className={`text-xs text-slate-600 block mt-0.5 ${isMine ? 'text-right mr-1' : 'ml-1'}`}>
          {message.timestamp.slice(11, 16)}
        </span>
      </div>
    </div>
  );
}
