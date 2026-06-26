const SUIT_MAP: Record<string, string> = {
  s: '\u2660',
  h: '\u2665',
  d: '\u2666',
  c: '\u2663',
};

const SUIT_COLOR: Record<string, 'red' | 'black'> = {
  s: 'black',
  h: 'red',
  d: 'red',
  c: 'black',
};

export function parseCard(card: string): { rank: string; suit: string; color: 'red' | 'black' } {
  const suit = card.slice(-1);
  const rank = card.slice(0, -1);
  return {
    rank: rank === 'T' ? '10' : rank,
    suit: SUIT_MAP[suit] || suit,
    color: SUIT_COLOR[suit] || 'black',
  };
}

export function rankToLabel(rank: string): string {
  const map: Record<string, string> = {
    A: 'A', K: 'K', Q: 'Q', J: 'J', T: '10',
    '9': '9', '8': '8', '7': '7', '6': '6',
    '5': '5', '4': '4', '3': '3', '2': '2',
  };
  return map[rank] || rank;
}
