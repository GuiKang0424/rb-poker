import { useState, useCallback } from 'react';
import { useGameContext } from '../context/GameContext';
import type { ActionType } from '../types/game';

export function ActionBar() {
  const { state, sendAction } = useGameContext();
  const [amount, setAmount] = useState('');

  const mySeat = state.mySeat;
  const isMyTurn = mySeat !== null && state.currentActor === mySeat;
  const req = state.actionRequest;
  const myPlayer = mySeat !== null ? state.players[mySeat] : null;

  const handleAction = useCallback(
    (action: ActionType, value?: number) => {
      if (action === 'bet' || action === 'raise') {
        sendAction(action, { amount: value });
      } else {
        sendAction(action);
      }
      setAmount('');
    },
    [sendAction],
  );

  if (!isMyTurn || !req || !myPlayer) {
    return (
      <div className="h-20 flex items-center justify-center text-slate-500 text-sm">
        {state.currentActor !== null
          ? `等待玩家 ${state.players[state.currentActor]?.nickname || state.currentActor} 行动...`
          : '等待下一手牌...'}
      </div>
    );
  }

  const toCall = req.toCall;
  const minRaise = req.minRaise;
  const currentBet = req.currentBet;
  const myChips = myPlayer.chips;
  const minBetAmount = state.blinds?.bigBlind || 10;
  const canCheck = toCall === 0;
  const canCall = toCall > 0 && myChips >= toCall;
  const canBet = currentBet === 0 && myChips >= minBetAmount;
  const canRaise = currentBet > 0 && myChips + myPlayer.currentBet > currentBet;
  const minRaiseTotal = currentBet + minRaise;

  const parsedAmount = parseInt(amount, 10) || 0;

  return (
    <div className="bg-slate-800 rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-300">
          需跟注: <span className="text-yellow-400 font-bold">{toCall}</span> | 最小加注: {minRaise}
        </span>
        <span className="text-sm text-slate-300">
          剩余筹码: <span className="text-green-400 font-bold">{myChips}</span>
        </span>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <button
          onClick={() => handleAction('fold')}
          className="px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg font-medium transition-colors"
        >
          弃牌
        </button>

        {canCheck && (
          <button
            onClick={() => handleAction('check')}
            className="px-4 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg font-medium transition-colors"
          >
            过牌
          </button>
        )}

        {canCall && (
          <button
            onClick={() => handleAction('call')}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium transition-colors"
          >
            跟注 {toCall}
          </button>
        )}

        {canBet && (
          <>
            <input
              type="number"
              min={minBetAmount}
              max={myChips}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={`下注金额 (最小 ${minBetAmount})`}
              className="px-3 py-2 bg-slate-700 rounded-lg text-sm w-40 focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <button
              onClick={() => handleAction('bet', parsedAmount)}
              disabled={parsedAmount < minBetAmount || parsedAmount > myChips}
              className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
            >
              下注
            </button>
          </>
        )}

        {canRaise && (
          <>
            <input
              type="number"
              min={minRaiseTotal}
              max={myChips + myPlayer.currentBet}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={`加注到 (最小 ${minRaiseTotal})`}
              className="px-3 py-2 bg-slate-700 rounded-lg text-sm w-44 focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <button
              onClick={() => handleAction('raise', parsedAmount)}
              disabled={parsedAmount < minRaiseTotal}
              className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
            >
              加注
            </button>
          </>
        )}

        <button
          onClick={() => handleAction('all_in')}
          disabled={myChips <= 0}
          className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
        >
          All-in {myChips}
        </button>
      </div>
    </div>
  );
}
