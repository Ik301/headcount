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
  "var(--n-spy)": "#4B4F93",
  "var(--n-affairs)": "#A8772A",
  "var(--n-politics)": "#5B7A2C",
  "var(--n-board)": "#8A6446",
  "var(--n-market)": "#2C7C86",
  "var(--n-defend)": "#C0612B",
  "var(--n-jokes)": "#7C867F",
};
const CYCLE = ["var(--n-spy)", "var(--n-board)", "var(--n-defend)", "var(--n-politics)", "var(--n-market)", "var(--n-affairs)", "var(--n-jokes)"];

export function narrativeColor(id: string, index = 0): string {
  return BY_ID[id] ?? CYCLE[index % CYCLE.length];
}

/** Canvas needs real hex values, not CSS variables. */
export function narrativeHex(id: string, index = 0): string {
  return HEX[narrativeColor(id, index)] ?? "#7C867F";
}
