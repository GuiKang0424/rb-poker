export interface UserInfo {
  id: string;
  username: string | null;
  chips: number;
  isAnonymous: boolean;
  totalHands: number;
  totalWins: number;
  totalProfit: number;
  createdAt: string;
  lastLoginAt: string;
}

export interface AuthState {
  user: UserInfo | null;
  token: string | null;
  loading: boolean;
}
