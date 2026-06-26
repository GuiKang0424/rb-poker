export type GameStage = 'waiting' | 'preflop' | 'flop' | 'turn' | 'river' | 'reveal_wait' | 'showdown' | 'hand_end';
export type PlayerStatus = 'waiting' | 'active' | 'folded' | 'all_in' | 'sitting_out';
export type ActionType = 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in' | 'start_hand' | 'leave' | 'show_hand' | 'reveal_choice';

export interface Player {
  seat: number;
  nickname: string;
  chips: number;
  status: PlayerStatus;
  currentBet: number;
  totalBetThisHand: number;  // 本手牌总投入（用于计算底池）
  holeCards?: string[];
  isDealer?: boolean;
  isSmallBlind?: boolean;
  isBigBlind?: boolean;
  isReady?: boolean;
  isOwner?: boolean;
}

export interface WaitingPlayer {
  userId: string;
  nickname: string;
}

export interface ServerEvent {
  type: string;
  data: any;
}

export interface ActionRequest {
  seat: number;
  toCall: number;
  minRaise: number;
  currentBet: number;
}

export interface JoinedData {
  seat: number | null;
  isOwner: boolean;
}

export interface RevealPhase {
  pending: boolean;
  pendingPlayers: number[];
  myChoiceMade: boolean;
  revealedHands?: Record<string, string[]>;
  uncontested?: boolean;  // 是否不战而胜
}

export interface GameState {
  stage: GameStage;
  dealerSeat: number;
  currentActor: number | null;
  communityCards: string[];
  players: Record<number, Player>;
  pot: number;
  roomId: string | null;
  mySeat: number | null;
  isOwner: boolean;
  actionRequest: ActionRequest | null;
  handResult: HandResult | null;
  blinds: { smallBlindSeat: number; bigBlindSeat: number; smallBlind: number; bigBlind: number } | null;
  waitingPlayers: WaitingPlayer[];
  revealPhase: RevealPhase | null;
  messages: ChatMessage[];
  error: string | null;
}

export interface HandResult {
  winners: number[][];
  pots: number[];
  showdown: boolean;
  revealed?: Record<string, string[]>;
}

export type Page = 'lobby' | 'game';

export type ChatMessageType = 'text' | 'quick' | 'system';

export interface ChatMessage {
  seat: number;
  userId: string;
  nickname: string;
  type: ChatMessageType;
  content: string;
  timestamp: string;
}
