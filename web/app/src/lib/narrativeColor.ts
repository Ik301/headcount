/* Narrative colours: the fixed demo taxonomy gets the brief's tokens; anything else (live checks)
 * cycles through the same muted set in order of appearance. */
const BY_ID: Record<string, string> = {
  n1: "var(--n-spy)",
  n2: "var(--n-affairs)",
  n3: "var(--n-politics)",
  n4: "var(--n-board)",
  n5: "var(--n-market)",
  n6: "var(--n-defend)",
  n7: "var(--n-jokes)",
};
const HEX: Record<string, string> = {
  "var(--n-spy)": "#6B5CA5",
  "var(--n-affairs)": "#B5853B",
  "var(--n-politics)": "#3E7C6A",
  "var(--n-board)": "#8C7A3D",
  "var(--n-market)": "#4F6FA8",
  "var(--n-defend)": "#A0527F",
  "var(--n-jokes)": "#8A8F99",
};
const CYCLE = ["var(--n-spy)", "var(--n-board)", "var(--n-defend)", "var(--n-politics)", "var(--n-market)", "var(--n-affairs)", "var(--n-jokes)"];

export function narrativeColor(id: string, index = 0): string {
  return BY_ID[id] ?? CYCLE[index % CYCLE.length];
}

/** Canvas needs real hex values, not CSS variables. */
export function narrativeHex(id: string, index = 0): string {
  return HEX[narrativeColor(id, index)] ?? "#8A8F99";
}
