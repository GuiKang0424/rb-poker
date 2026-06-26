import { Card } from './Card';
import type { Player } from '../types/game';

interface PlayerSeatProps {
  player: Player;
  isCurrentActor: boolean;
  isMySeat: boolean;
}

export function PlayerSeat({ player, isCurrentActor, isMySeat }: PlayerSeatProps) {
  const statusLabels: Record<string, string> = {
    waiting: '等待中',
    active: '游戏中',
    folded: '已弃牌',
    all_in: 'All-in',
    sitting_out: '离座',
  };

  const statusColors: Record<string, string> = {
    waiting: 'bg-slate-500',
    active: 'bg-green-600',
    folded: 'bg-red-600',
    all_in: 'bg-yellow-600',
    sitting_out: 'bg-gray-500',
  };

  return (
    <div
      className={`
        relative flex flex-col items-center gap-1 p-2 rounded-xl
        transition-all duration-300 min-w-[100px]
        ${isCurrentActor ? 'ring-2 ring-yellow-400 animate-pulse' : ''}
        ${isMySeat ? 'bg-slate-800/80' : 'bg-slate-800/50'}
      `}
    >
      {/* Dealer / Blind / Owner / Ready badges */}
      <div className="absolute -top-2 -left-2 flex gap-0.5">
        {player.isDealer && (
          <span className="w-5 h-5 bg-blue-500 rounded-full text-xs flex items-center justify-center font-bold">D</span>
        )}
        {player.isSmallBlind && (
          <span className="w-5 h-5 bg-yellow-500 rounded-full text-xs flex items-center justify-center font-bold text-slate-900">SB</span>
        )}
        {player.isBigBlind && (
          <span className="w-5 h-5 bg-orange-500 rounded-full text-xs flex items-center justify-center font-bold">BB</span>
        )}
        {player.isOwner && (
          <span className="w-5 h-5 bg-purple-500 rounded-full text-xs flex items-center justify-center font-bold" title="房主">主</span>
        )}
        {player.isReady && (
          <span className="w-5 h-5 bg-green-500 rounded-full text-xs flex items-center justify-center font-bold" title="已准备">✓</span>
        )}
      </div>

      {/* Nickname */}
      <div className="text-sm font-medium truncate max-w-[90px]">
        {player.nickname}
        {isMySeat && <span className="text-xs text-blue-400 ml-1">(我)</span>}
      </div>

      {/* Status chip */}
      <span className={`text-[10px] px-2 py-0.5 rounded-full text-white ${statusColors[player.status] || 'bg-slate-500'}`}>
        {statusLabels[player.status] || player.status}
      </span>

      {/* Chips */}
      <div className="text-xs text-slate-300">
        💰 {player.chips}
      </div>

      {/* Current bet */}
      {player.currentBet > 0 && (
        <div className="text-xs text-yellow-400 font-semibold">
          下注: {player.currentBet}
        </div>
      )}

      {/* Hole cards */}
      <div className="flex gap-1 mt-1">
        {player.holeCards ? (
          player.holeCards.map((c, i) => <Card key={i} card={c} />)
        ) : (
          <>
            <Card card="" hidden />
            <Card card="" hidden />
          </>
        )}
      </div>
    </div>
  );
}
