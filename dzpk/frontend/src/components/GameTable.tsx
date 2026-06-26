import { useMemo, useState, useCallback, useEffect } from 'react';
import { useGameContext } from '../context/GameContext';
import { PlayerSeat } from './PlayerSeat';
import { ActionBar } from './ActionBar';
import { Card } from './Card';
import { ChatPanel } from './ChatPanel/ChatPanel';

function ErrorToast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [message, onDismiss]);

  return (
    <div className="mx-4 mt-2 px-4 py-2 bg-red-600/90 rounded-lg text-sm text-white flex items-center justify-between">
      <span>{message}</span>
      <button onClick={onDismiss} className="ml-3 text-white/70 hover:text-white">&times;</button>
    </div>
  );
}

function getSeatPosition(index: number, total: number, radiusX: number, radiusY: number) {
  const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
  return {
    x: Math.cos(angle) * radiusX,
    y: Math.sin(angle) * radiusY,
  };
}

export function GameTable() {
  const { state, dispatch, ready, unready, startGame, setPage, sendAction } = useGameContext();
  const [showBuyIn, setShowBuyIn] = useState(false);
  const [buyInChips, setBuyInChips] = useState(1000);
  const [leaving, setLeaving] = useState(false);
  const players = state.players;
  const maxPlayers = 9;
  const seatedIndices = Object.keys(players).map(Number).sort((a, b) => a - b);

  const myPlayer = state.mySeat !== null ? players[state.mySeat] : null;
  const isInWaiting = state.mySeat === null;
  const isInGame = state.stage !== 'waiting' && state.stage !== 'hand_end' && state.stage !== 'reveal_wait';
  const canStartGame = !isInGame
    && state.isOwner
    && seatedIndices.length >= 2
    && seatedIndices.every((s) => players[s]?.isReady);

  const pot = useMemo(() => {
    // 用 totalBetThisHand 计算总底池（所有玩家这手牌投入的总筹码）
    const totalPot = Object.values(players).reduce((sum, p) => sum + (p.totalBetThisHand || 0), 0);
    return totalPot;
  }, [players]);

  const stageLabels: Record<string, string> = {
    waiting: '等待中',
    preflop: '翻牌前',
    flop: '翻牌',
    turn: '转牌',
    river: '河牌',
    reveal_wait: '展示阶段',
    showdown: '摊牌',
    hand_end: '牌局结束',
  };

  const handleReady = useCallback(() => {
    setBuyInChips(1000);
    setShowBuyIn(true);
  }, []);

  const confirmReady = useCallback(() => {
    setShowBuyIn(false);
    ready(buyInChips);
  }, [ready, buyInChips]);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-4">
          <span className="text-lg font-bold">德州扑克</span>
          <span className="text-sm text-slate-400">房间: {state.roomId}</span>
          <span className="text-sm px-2 py-0.5 bg-blue-600 rounded-full">
            {stageLabels[state.stage] || state.stage}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {state.blinds && (
            <span className="text-sm text-slate-400">
              盲注: {state.blinds.smallBlind}/{state.blinds.bigBlind}
            </span>
          )}
          {/* Owner start game button */}
          {state.isOwner && (
            <button
              onClick={startGame}
              disabled={!canStartGame}
              className="px-3 py-1 bg-green-600 hover:bg-green-500 disabled:bg-slate-600 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors"
            >
              开始游戏
            </button>
          )}
          {/* Ready / Unready */}
          {!isInGame && !state.isOwner && (
            <>
              {isInWaiting ? (
                <button
                  onClick={handleReady}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-sm font-medium transition-colors"
                >
                  准备
                </button>
              ) : myPlayer?.isReady ? (
                <button
                  onClick={unready}
                  className="px-3 py-1 bg-yellow-600 hover:bg-yellow-500 rounded text-sm font-medium transition-colors"
                >
                  取消准备
                </button>
              ) : null}
            </>
          )}
          <button
            onClick={() => {
              if (leaving) return;
              setLeaving(true);
              sendAction('leave');
              setTimeout(() => setPage('lobby'), 200);
            }}
            disabled={leaving}
            className="px-3 py-1 bg-slate-600 hover:bg-slate-500 disabled:bg-slate-700 rounded text-sm transition-colors"
          >
            {leaving ? '离开中...' : '离开'}
          </button>
        </div>
      </div>

      {/* Error toast */}
      {state.error && <ErrorToast message={state.error} onDismiss={() => dispatch({ type: 'CLEAR_ERROR' })} />}

      {/* Main area: table + waiting sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Table area */}
        <div className="flex-1 relative overflow-hidden flex items-center justify-center">
          {/* Table felt */}
          <div
            className="relative bg-green-800 rounded-[50%] border-8 border-amber-900 shadow-2xl"
            style={{ width: 'min(90vw, 800px)', height: 'min(55vw, 480px)', maxWidth: '90vw', maxHeight: '60vh' }}
          >
            {/* Center: community cards + pot */}
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              {pot > 0 && (
                <div className="bg-slate-900/70 px-4 py-1 rounded-full text-yellow-400 font-bold text-lg">
                  底池: {pot}
                </div>
              )}

              <div className="flex gap-2">
                {state.communityCards.map((card, i) => (
                  <Card key={i} card={card} />
                ))}
                {Array.from({ length: 5 - state.communityCards.length }).map((_, i) => (
                  <Card key={`empty-${i}`} card="" hidden />
                ))}
              </div>

              {/* 展示阶段：等待玩家选择是否展示手牌 */}
              {state.revealPhase?.pending && (
                <div className="bg-slate-900/80 px-4 py-3 rounded-lg text-center space-y-3">
                  <div className="text-sm text-slate-300">
                    {state.revealPhase.uncontested ? '不战而胜 - 手牌展示阶段' : '手牌展示阶段'}
                  </div>
                  {!state.revealPhase.uncontested && (
                    <div className="text-xs text-slate-400">
                      等待玩家选择：{state.revealPhase.pendingPlayers.map(s => state.players[s]?.nickname || s).join(', ')}
                    </div>
                  )}
                  {/* 已展示的手牌 */}
                  {state.revealPhase.revealedHands && Object.keys(state.revealPhase.revealedHands).length > 0 && (
                    <div className="space-y-2">
                      {Object.entries(state.revealPhase.revealedHands).map(([seatStr, cards]) => {
                        const seat = parseInt(seatStr);
                        const nickname = state.players[seat]?.nickname || `座位${seat}`;
                        return (
                          <div key={seatStr} className="flex items-center justify-center gap-1">
                            <span className="text-xs text-slate-400 mr-2">{nickname}:</span>
                            {cards.map((card, i) => (
                              <Card key={i} card={card} small />
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {/* 展示/不展示按钮 */}
                  {state.mySeat !== null && !state.revealPhase.myChoiceMade && state.revealPhase.pendingPlayers.includes(state.mySeat) && (
                    <div className="flex gap-3 justify-center">
                      <button
                        onClick={() => sendAction('reveal_choice', { choice: true })}
                        className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded font-medium transition-colors"
                      >
                        展示手牌
                      </button>
                      <button
                        onClick={() => sendAction('reveal_choice', { choice: false })}
                        className="px-4 py-2 bg-slate-600 hover:bg-slate-500 rounded font-medium transition-colors"
                      >
                        不展示
                      </button>
                    </div>
                  )}
                  {state.revealPhase.myChoiceMade && (
                    <div className="text-xs text-slate-400">等待其他玩家选择...</div>
                  )}
                </div>
              )}

              {/* 牌局结束：显示结果 */}
              {state.handResult && (
                <div className="bg-slate-900/80 px-4 py-3 rounded-lg text-center space-y-3">
                  <div className="text-sm text-slate-300">
                    {state.handResult.showdown ? '摊牌结果' : '不战而胜'}
                  </div>
                  <div className="text-yellow-400 font-bold">
                    {state.handResult.winners.map((ws, i) => (
                      <span key={i} className="block">
                        赢家: {ws.map(s => state.players[s]?.nickname || s).join(', ')}
                        (池 {state.handResult!.pots[i] || 0})
                      </span>
                    ))}
                  </div>
                  {/* 已展示的手牌 */}
                  {state.handResult.revealed && Object.keys(state.handResult.revealed).length > 0 && (
                    <div className="space-y-2">
                      {Object.entries(state.handResult.revealed).map(([seatStr, cards]) => {
                        const seat = parseInt(seatStr);
                        const nickname = state.players[seat]?.nickname || `座位${seat}`;
                        return (
                          <div key={seatStr} className="flex items-center justify-center gap-1">
                            <span className="text-xs text-slate-400 mr-2">{nickname}:</span>
                            {cards.map((card, i) => (
                              <Card key={i} card={card} small />
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {/* 下一局按钮 */}
                  {state.mySeat !== null && state.players[state.mySeat] && (
                    <button
                      onClick={() => ready(0)} // 复用 ready，0 表示不改变筹码
                      disabled={state.players[state.mySeat]?.isReady}
                      className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                        state.players[state.mySeat]?.isReady
                          ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                          : 'bg-green-600 hover:bg-green-500 text-white'
                      }`}
                    >
                      {state.players[state.mySeat]?.isReady ? '已准备下一局' : '下一局'}
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Player seats around table */}
            {seatedIndices.map((seatIdx) => {
              const pos = getSeatPosition(seatIdx, maxPlayers, 42, 48);
              const player = players[seatIdx];
              if (!player) return null;
              const isDealer = state.dealerSeat === seatIdx;
              const p = { ...player, isDealer };
              return (
                <div
                  key={seatIdx}
                  className="absolute"
                  style={{
                    left: `${50 + pos.x}%`,
                    top: `${50 + pos.y}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                >
                  <PlayerSeat
                    player={p}
                    isCurrentActor={state.currentActor === seatIdx}
                    isMySeat={state.mySeat === seatIdx}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Chat panel */}
        <ChatPanel />

        {/* Waiting area sidebar */}
        <div className="w-56 bg-slate-800/50 border-l border-slate-700 p-3 flex flex-col">
          <h3 className="text-sm font-semibold text-slate-400 mb-2">
            等待区 ({state.waitingPlayers.length})
          </h3>
          <div className="flex-1 space-y-1 overflow-y-auto">
            {state.waitingPlayers.length === 0 ? (
              <p className="text-xs text-slate-600">暂无等待玩家</p>
            ) : (
              state.waitingPlayers.map((wp) => (
                <div key={wp.userId} className="text-xs text-slate-300 px-2 py-1 bg-slate-700/50 rounded">
                  {wp.nickname}
                </div>
              ))
            )}
          </div>

          {/* My status */}
          {isInWaiting && (
            <div className="mt-3 pt-3 border-t border-slate-700">
              <p className="text-xs text-slate-500 mb-2">你在等待区</p>
              {!state.isOwner && (
                <button
                  onClick={handleReady}
                  className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-medium transition-colors"
                >
                  准备入座
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Action bar */}
      <div className="px-4 pb-4">
        <ActionBar />
      </div>

      {/* Buy-in modal */}
      {showBuyIn && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 w-80 shadow-2xl">
            <h2 className="text-lg font-bold mb-4">设置买入筹码</h2>
            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-2">
                买入筹码 (100 - 10000)
              </label>
              <input
                type="number"
                min={100}
                max={10000}
                value={buyInChips}
                onChange={(e) => setBuyInChips(Math.max(100, Math.min(10000, parseInt(e.target.value) || 1000)))}
                className="w-full px-4 py-3 bg-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white text-lg"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowBuyIn(false)}
                className="flex-1 px-4 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg font-medium transition-colors"
              >
                取消
              </button>
              <button
                onClick={confirmReady}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium transition-colors"
              >
                确认 ({buyInChips})
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
