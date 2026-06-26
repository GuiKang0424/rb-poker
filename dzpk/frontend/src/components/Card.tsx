import { parseCard } from '../utils/card';

interface CardProps {
  card: string;
  hidden?: boolean;
  small?: boolean;
}

export function Card({ card, hidden, small }: CardProps) {
  const sizeClass = small ? 'w-8 h-11' : 'w-12 h-16 md:w-14 md:h-20';
  const textSizeClass = small ? 'text-sm' : 'text-lg md:text-xl';

  if (hidden) {
    return (
      <div className={`${sizeClass} bg-slate-600 rounded-lg border-2 border-slate-500 flex items-center justify-center shadow-md`}>
        {!small && <div className="w-8 h-10 md:w-10 md:h-14 border-2 border-dashed border-slate-400 rounded"></div>}
      </div>
    );
  }

  const { rank, suit, color } = parseCard(card);
  const colorClass = color === 'red' ? 'text-red-600' : 'text-slate-900';

  return (
    <div className={`${sizeClass} bg-white rounded-lg border border-slate-300 flex flex-col items-center justify-center shadow-md select-none`}>
      <span className={`${textSizeClass} font-bold ${colorClass}`}>{rank}</span>
      <span className={`${textSizeClass} ${colorClass}`}>{suit}</span>
    </div>
  );
}
