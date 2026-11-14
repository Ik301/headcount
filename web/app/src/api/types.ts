/* Shapes from docs/DEMO.md ("API contracts") and README.md ("site_data.json").
 * Everything beyond the contract is optional: the UI must render with any field missing. */

export interface Evidence {
  post_uri?: string;
  t?: string;
  note?: string;
  trace?: string;
  text?: string;
  public_handle?: string | null;
  p_automated?: number;
}

export interface ExamplePost {
  text: string;
  public_handle?: string | null;
}

export interface ClaimNarrative {
  id: string;
  label: string;
  side?: string;
  posts?: number;
  share_of_matches: number;
  bot_post_share: number;
  bot_post_share_ci?: [number, number];
  baseline_bot_share?: number;
  example_posts?: ExamplePost[];
  evidence?: Evidence[];
}

export interface Commonality {
  signal: string;
  accounts: number;
  evidence?: Evidence[];
}

export interface ArchetypeMix {
  id: string;
  label: string;
  share: number;
  lift?: number | null;
  lift_ci?: [number, number];
}

export interface ClaimNews {
  headlines?: { t?: string; outlet?: string; title: string; url?: string; funding?: string; narrative?: string; hedged?: boolean }[];
  hedging_rate?: number;
  social_hedging_rate?: number;
  narratives_in_news?: string[];
  social_only?: string[];
}

export interface ClaimResult {
  claim_id: string;
  claim: string;
  scope?: "corpus" | "live" | string;
  matched_posts: number;
  window?: { from?: string | null; to?: string | null };
  narratives: ClaimNarrative[];
  bot_commonalities?: Commonality[];
  amplifiers?: { n_humans: number; archetype_mix: ArchetypeMix[]; note?: string };
  baseline_bot_share?: number;
  chart_png_url?: string;
  dashboard_url?: string;
  reply_text?: string;
  seconds?: number;
  news?: ClaimNews;
  error?: string;
}

/* ---------------- site_data.json ---------------- */

export interface StoryEvent {
  t: string;
  label: string;
  major?: boolean;
  source?: string;
}

export interface SiteNarrative {
  id: string;
  label: string;
  side?: string;
  posts?: number;
  bot_posts?: number;
  share?: number;
  share_without_bots?: number;
  bot_post_share: number;
  bot_post_share_ci?: [number, number];
  bot_account_share?: number;
  examples?: (string | ExamplePost)[];
  threshold_strip?: Record<string, number>;
  evidence?: Evidence[];
  color?: string;
}

export interface GraphNode {
  id: string;
  narrative?: string;
  archetype?: string | null;
  p_automated?: number;
  public_handle?: string | null;
  self_label_bot?: boolean;
  size?: number;
  /** First appearance: ISO time or hour index from story start. Any of these names. */
  t?: string | number;
  first_t?: string | number;
  hour?: number;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  s: string;
  t: string;
  type?: string;
  /** Edge appearance time (ISO or hour index), optional. */
  at?: string | number;
}

export interface SiteArchetype {
  id: string;
  label: string;
  size?: number;
  share?: number;
  lift?: number;
  lift_ci?: [number, number];
  features?: Record<string, string | number> | { value: string | number; label: string }[];
  mix?: Record<string, number>;
  median_delay?: string;
  public_examples?: string[];
  evidence?: Evidence[];
}

export interface Cluster {
  cluster_id: string;
  narrative?: string;
  size?: number;
  dids?: string[];
  reasons?: string[];
  evidence?: Evidence[];
  window?: { from?: string; to?: string };
  text?: string;
}

export interface Finding {
  view?: string;
  text: string;
  source?: string;
}

export interface SiteNews {
  outlets?: { name: string; funding?: string }[];
  headlines?: { t?: string; outlet?: string; title: string; url?: string; narrative?: string; hedged?: boolean }[];
  hedging?: { news?: number; social?: number; topic?: string };
  narratives_in_news?: string[];
  social_only?: string[];
}

export interface ChallengeItem {
  account_ref: string;
  public_handle?: string | null;
  posts?: (string | { t?: string; text: string })[];
  p_automated?: number;
  reasons?: string[];
  hand_label?: string | null;
}

export interface SiteData {
  story?: {
    title?: string;
    window?: { from?: string; to?: string };
    events?: StoryEvent[];
    totals?: { posts?: number; accounts?: number; engagements?: number; self_labeled_bots?: number };
    baseline_bot_share?: number;
    claim?: string;
    data_through?: string;
    sample?: boolean;
  };
  timeline?: { hour: string; posts: number; by_narrative?: Record<string, number>; bots_by_narrative?: Record<string, number> }[];
  narratives?: SiteNarrative[];
  graph?: { nodes?: GraphNode[]; edges?: GraphEdge[]; cap_note?: string };
  archetypes?: SiteArchetype[];
  clusters?: Cluster[];
  coordination?: Cluster[];
  public_accounts?: { handle: string; narratives?: string[]; p_automated?: number; top_posts?: unknown[] }[];
  validation?: {
    recall_at_k?: Record<string, number>;
    retrieval_recall_at_k?: Record<string, number>;
    ablation?: Record<string, unknown>;
    gold_accuracy?: number;
    gold_by_narrative?: Record<string, number>;
    model_version?: string;
  };
  challenge?: ChallengeItem[] | { accounts?: ChallengeItem[] };
  findings?: Finding[] | Record<string, string | Finding>;
  news?: SiteNews;
}
