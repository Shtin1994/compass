import { PostAnalysis } from "./insight";

// Тип для строки в основной таблице
export interface PostForTable {
  id: number;
  telegram_id: number;
  channel_name: string;
  text: string | null;
  created_at: string;
  comments_count: number;
  views_count: number | null;
  has_analysis: boolean;
}

// Тип для пагинированного ответа
export interface PaginatedPostsResponse {
  total: number;
  page: number;
  size: number;
  items: PostForTable[];
}

// Тип для детальной информации о посте (в боковой панели)
export interface PostDetailsData extends PostForTable {
  reactions: { [key: string]: number } | null;
  media: { type: string } | null;
  forward_info: object | null; // Упрощенно
  analysis: PostAnalysis | null;
}