import { QUICK_PHRASE_LIST } from './ChatMessage';

interface Props {
  onSend: (phraseId: number) => void;
}

export function QuickPhrases({ onSend }: Props) {
  return (
    <div className="grid grid-cols-4 gap-1">
      {QUICK_PHRASE_LIST.map(({ id, text }) => (
        <button
          key={id}
          onClick={() => onSend(id)}
          className="px-1 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs text-slate-300 transition-colors truncate"
          title={text}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
