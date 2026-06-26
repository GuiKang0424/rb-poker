import React, { createContext, useContext, useReducer, useCallback, useRef } from 'react';
import type {
  GameState,
  Player,
  ActionType,
  ServerEvent,
  Page,
  ChatMessage,
} from '../types/game';

function generateUserId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function getOrCreateUserId(): string {
  let id = localStorage.getItem('dzpk_userId');
  if (!id) {
    id = generateUserId();
    localStorage.setItem('dzpk_userId', id);
  }
  return id;
}

const initialState: GameState = {
  stage: 'waiting',
  dealerSeat: -1,
  currentActor: null,
  communityCards: [],
  players: {},
  pot: 0,
  roomId: null,
  mySeat: null,
  isOwner: false,
  actionRequest: null,
  handResult: null,
  blinds: null,
  waitingPlayers: [],
  revealPhase: null,
  messages: [],
  error: null,
};

type Action =
  | { type: 'RESET' }
  | { type: 'SET_ROOM'; roomId: string }
  | { type: 'SERVER_EVENT'; event: ServerEvent }
  | { type: 'SET_PAGE'; page: Page }
  | { type: 'CLEAR_ERROR' };

function gameReducer(state: GameState, action: Action): GameState {
  switch (action.type) {
    case 'RESET':
      return { ...initialState };
    case 'CLEAR_ERROR':
      return { ...state, error: null };

    case 'SET_ROOM':
      return { ...initialState, roomId: action.roomId };

    case 'SERVER_EVENT': {
      const { type, data } = action.event;
      switch (type) {
        case 'player_join': {
          const p: Player = {
            seat: data.seat,
            nickname: data.nickname,
            chips: data.chips,
            status: 'waiting',
            currentBet: 0,
            totalBetThisHand: 0,
            isReady: data.isReady ?? false,
            isOwner: data.isOwner ?? false,
          };
          return {
            ...state,
            players: { ...state.players, [data.seat]: p },
          };
        }
        case 'player_leave': {
          const copy = { ...state.players };
          delete copy[data.seat];
          return {
            ...state,
            players: copy,
            mySeat: data.seat === state.mySeat ? null : state.mySeat,
          };
        }
        case 'state_change': {
          // preflop 时重置玩家状态（新一手牌开始）
          const isPreflop = data.state === 'preflop';
          // 进入新下注轮时重置 currentBet（flop/turn/river 都需要）
          const shouldResetBet = ['preflop', 'flop', 'turn', 'river'].includes(data.state);
          const resetPlayers = shouldResetBet
            ? Object.fromEntries(
                  Object.entries(state.players).map(([k, p]) => [
                    k,
                    {
                      ...p,
                      currentBet: 0,
                      totalBetThisHand: isPreflop ? 0 : p.totalBetThisHand,
                      isDealer: false,
                      isSmallBlind: false,
                      isBigBlind: false,
                      status:
                        p.status === 'folded' || p.status === 'all_in'
                          ? 'active'
                          : p.status,
                    },
                  ]),
                )
              : state.players;
          return {
            ...state,
            stage: data.state,
            dealerSeat: data.dealerSeat ?? state.dealerSeat,
            communityCards:
              data.state === 'preflop' || data.state === 'waiting'
                ? []
                : state.communityCards,
            handResult:
              data.state === 'preflop' || data.state === 'waiting'
                ? null
                : state.handResult,
            blinds:
              data.state === 'preflop' || data.state === 'waiting'
                ? null
                : state.blinds,
            players: resetPlayers,
          };
        }
        case 'hole_cards': {
          if (data.seat !== state.mySeat) return state;
          const me = state.players[data.seat];
          if (!me) return state;
          return {
            ...state,
            players: {
              ...state.players,
              [data.seat]: { ...me, holeCards: data.cards },
            },
          };
        }
        case 'community_cards': {
          const newCards = data.cards as string[];
          return {
            ...state,
            communityCards: [...state.communityCards, ...newCards],
          };
        }
        case 'action_request': {
          return {
            ...state,
            currentActor: data.seat,
            actionRequest: {
              seat: data.seat,
              toCall: data.toCall,
              minRaise: data.minRaise,
              currentBet: data.currentBet,
            },
          };
        }
        case 'player_action': {
          const p = state.players[data.seat];
          if (!p) return state;
          const newStatus =
            data.action === 'fold'
              ? 'folded'
              : data.chipsLeft === 0
                ? 'all_in'
                : p.status;
          return {
            ...state,
            players: {
              ...state.players,
              [data.seat]: {
                ...p,
                currentBet: data.totalBet,
                totalBetThisHand: data.totalBetThisHand ?? p.totalBetThisHand,
                chips: data.chipsLeft,
                status: newStatus,
              },
            },
          };
        }
        case 'blinds_posted': {
          const { smallBlindSeat, bigBlindSeat, smallBlind, bigBlind, smallBlindTotalBet, bigBlindTotalBet } = data;
          const players = { ...state.players };
          if (players[smallBlindSeat]) {
            players[smallBlindSeat] = {
              ...players[smallBlindSeat],
              isSmallBlind: true,
              isBigBlind: false,
              currentBet: smallBlind,
              totalBetThisHand: smallBlindTotalBet ?? smallBlind,
            };
          }
          if (players[bigBlindSeat]) {
            players[bigBlindSeat] = {
              ...players[bigBlindSeat],
              isSmallBlind: false,
              isBigBlind: true,
              currentBet: bigBlind,
              totalBetThisHand: bigBlindTotalBet ?? bigBlind,
            };
          }
          return {
            ...state,
            players,
            blinds: { smallBlindSeat, bigBlindSeat, smallBlind, bigBlind },
          };
        }
        case 'hand_end': {
          return {
            ...state,
            stage: 'hand_end',
            currentActor: null,
            actionRequest: null,
            handResult: {
              winners: data.winners,
              pots: data.pots,
              showdown: data.showdown,
              revealed: data.revealed || {},
            },
          };
        }
        case 'hand_revealed': {
          // 玩家主动展示手牌（旧逻辑，保留兼容）
          const currentRevealed = state.handResult?.revealed || {};
          return {
            ...state,
            handResult: state.handResult
              ? {
                  ...state.handResult,
                  revealed: {
                    ...currentRevealed,
                    [data.seat]: data.cards,
                  },
                }
              : null,
          };
        }
        case 'reveal_phase_start': {
          // 进入手牌展示阶段
          return {
            ...state,
            stage: 'reveal_wait',
            revealPhase: {
              pending: true,
              pendingPlayers: data.pendingPlayers,
              myChoiceMade: false,
              uncontested: data.uncontested || false,  // 是否不战而胜
            },
            handResult: null,
          };
        }
        case 'player_revealed': {
          // 玩家做出了展示选择
          const newRevealed = data.revealed && data.cards
            ? { ...state.revealPhase?.revealedHands, [data.seat]: data.cards }
            : state.revealPhase?.revealedHands;

          return {
            ...state,
            revealPhase: state.revealPhase
              ? {
                  ...state.revealPhase,
                  myChoiceMade: data.seat === state.mySeat ? true : state.revealPhase.myChoiceMade,
                  revealedHands: newRevealed,
                }
              : null,
          };
        }
        case 'showdown_result': {
          // 展示阶段结束，显示最终结果
          return {
            ...state,
            stage: 'hand_end',
            revealPhase: null,
            handResult: {
              winners: data.winners,
              pots: data.pots,
              showdown: data.showdown ?? true,  // 不战而胜时为 false
              revealed: data.revealedHands || {},
            },
          };
        }
        case 'joined': {
          return { ...state, mySeat: data.seat, isOwner: data.isOwner ?? false };
        }
        case 'player_ready': {
          const pr = state.players[data.seat];
          if (!pr) return state;
          return {
            ...state,
            players: {
              ...state.players,
              [data.seat]: { ...pr, isReady: data.isReady, chips: data.chips ?? pr.chips },
            },
          };
        }
        case 'waiting_update': {
          return { ...state, waitingPlayers: data.players || [] };
        }
        case 'start_game_rejected': {
          return { ...state, error: data.reason || '开始游戏失败' };
        }
        case 'ready_rejected': {
          return { ...state, error: data.reason || '准备失败' };
        }
        case 'action_rejected': {
          return { ...state, error: data.reason || '操作无效' };
        }
        case 'chat_message': {
          const msg: ChatMessage = {
            seat: data.seat,
            userId: data.userId,
            nickname: data.nickname,
            type: data.type,
            content: data.content,
            timestamp: data.timestamp,
          };
          return {
            ...state,
            messages: [...state.messages, msg],
          };
        }
        case 'chat_history': {
          const history: ChatMessage[] = (data.messages || []).map((m: any) => ({
            seat: m.seat,
            userId: m.userId,
            nickname: m.nickname,
            type: m.type,
            content: m.content,
            timestamp: m.timestamp,
          }));
          return {
            ...state,
            messages: history,
          };
        }
        default:
          return state;
      }
    }

    default:
      return state;
  }
}

interface GameContextValue {
  state: GameState;
  dispatch: React.Dispatch<Action>;
  sendAction: (action: ActionType, data?: Record<string, unknown>) => void;
  sendChat: (type: string, content?: string, phraseId?: number) => void;
  joinRoom: (roomId: string, nickname: string, authUserId?: string) => void;
  ready: (chips?: number) => void;
  unready: () => void;
  startGame: () => void;
  page: Page;
  setPage: (page: Page) => void;
  sendRef: React.MutableRefObject<(msg: object) => void>;
}

const GameContext = createContext<GameContextValue | null>(null);

export function GameProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const [page, setPage] = React.useState<Page>('lobby');
  const sendRef = useRef<(msg: object) => void>(() => {});

  const setPageWrapped = useCallback((p: Page) => {
    setPage(p);
    if (p === 'lobby') {
      dispatch({ type: 'RESET' });
    }
  }, []);

  const sendAction = useCallback(
    (action: ActionType, data?: Record<string, unknown>) => {
      sendRef.current({ action, data });
    },
    [],
  );

  const joinRoom = useCallback(
    (roomId: string, nickname: string, authUserId?: string) => {
      const userId = authUserId || getOrCreateUserId();
      sendRef.current({
        action: 'join_room',
        data: { roomId, nickname, userId },
      });
    },
    [],
  );

  const ready = useCallback(
    (chips?: number) => {
      sendRef.current({
        action: 'ready',
        data: { chips },
      });
    },
    [],
  );

  const unready = useCallback(() => {
    sendRef.current({ action: 'unready', data: {} });
  }, []);

  const startGame = useCallback(() => {
    sendRef.current({ action: 'start_game', data: {} });
  }, []);

  const sendChat = useCallback(
    (type: string, content?: string, phraseId?: number) => {
      if (type === 'text') {
        sendRef.current({ action: 'chat', data: { type: 'text', content: content || '' } });
      } else if (type === 'quick') {
        sendRef.current({ action: 'chat', data: { type: 'quick', phrase_id: phraseId ?? 0 } });
      }
    },
    [],
  );

  const value: GameContextValue = {
    state,
    dispatch,
    sendAction,
    sendChat,
    joinRoom,
    ready,
    unready,
    startGame,
    page,
    setPage: setPageWrapped,
    sendRef,
  };

  return (
    <GameContext.Provider value={value}>
      {children}
    </GameContext.Provider>
  );
}

export function useGameContext() {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGameContext must be used within GameProvider');
  return ctx;
}
