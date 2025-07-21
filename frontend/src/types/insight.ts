export interface PostAnalysis {
  summary: string | null;
  sentiment: { [key: string]: number } | null;
  key_topics: string[] | null;
  model_used: string | null;
  generated_at: string; // Даты приходят как строки
}

export interface InsightCardData {
  post_id: number;
  post_telegram_id: number;
  post_text: string | null;
  post_created_at: string;
  channel_name: string;
  analysis: PostAnalysis;
}

export interface PaginatedInsightsResponse {
  total: number;
  page: number;
  size: number;
  items: InsightCardData[];
}