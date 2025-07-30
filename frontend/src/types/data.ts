// frontend/src/types/data.ts

import { PostAnalysis } from "./insight";

// --- НОВЫЕ ТИПЫ ДЛЯ КОММЕНТАРИЕВ ---

// Тип для одного комментария. Добавлен author_name для совместимости.
export interface Comment {
  id: number;
  post_id: number;
  text: string;
  created_at: string; // ISO 8601 string format
  author_name?: string | null; // Имя автора, если есть
}

// Тип для ответа API со списком комментариев и пагинацией. КЛЮЧЕВОЙ ТИП!
export interface PaginatedCommentsResponse {
  total: number;
  page: number;
  size: number;
  items: Comment[];
}


// --- СУЩЕСТВУЮЩИЕ ТИПЫ (остаются без изменений) ---

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

// Тип для пагинированного ответа для постов
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
  forward_info: object | null;
  analysis: PostAnalysis | null;
}