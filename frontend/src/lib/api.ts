// --- START OF FILE frontend/src/lib/api.ts ---

// ==============================================================================
// КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
// Этот файл — наш централизованный API-клиент. Он является "мостом" между
// фронтенд-компонентами и бэкенд-сервером.
// Его задачи:
// 1. Определять типы данных, которыми мы обмениваемся с сервером.
// 2. Предоставлять функции для выполнения всех необходимых API-запросов.
// 3. Обрабатывать ответы и ошибки в одном месте (handleResponse).
// Централизация API-логики здесь упрощает тестирование и дальнейшую поддержку.
// ==============================================================================

import { QueryClient } from '@tanstack/react-query';
import { Channel } from '@/types/channel';
import { PaginatedInsightsResponse } from '@/types/insight';
import { DynamicsDataPoint, SentimentDataPoint, TopicDataPoint } from '@/types/analytics';
import { PostDetailsData, PaginatedPostsResponse, PaginatedCommentsResponse } from '@/types/data';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
if (!API_BASE_URL) {
    throw new Error("Переменная окружения NEXT_PUBLIC_API_BASE_URL не установлена!");
}

export const queryClient = new QueryClient();

// Универсальный обработчик ответов API для уменьшения дублирования кода
const handleResponse = async (response: Response) => {
  const responseBody = await response.json().catch(() => ({ detail: response.statusText }));
  if (!response.ok) {
    const errorMessage = responseBody.detail || `Произошла ошибка, статус: ${response.status}`;
    throw new Error(errorMessage);
  }
  return responseBody;
};

// ДОБАВЛЕНО: Этот тип был определен в предыдущих шагах, но важно
// убедиться, что он здесь есть. Он описывает структуру тела запроса
// для сбора постов и является зеркалом Pydantic-схемы на бэкенде.
export type PostsCollectionRequestBody = {
  mode: 'get_new' | 'historical' | 'initial';
  date_from?: string | null;
  date_to?: string | null;
  limit?: number | null;
};

export const api = {
  // --- Каналы ---
  getChannels: async (): Promise<Channel[]> => {
    const response = await fetch(`${API_BASE_URL}/channels`);
    return handleResponse(response);
  },

  addChannel: async (username: string): Promise<Channel> => {
    const response = await fetch(`${API_BASE_URL}/channels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });
    return handleResponse(response);
  },

  updateChannelStatus: async (id: number, isActive: boolean): Promise<Channel> => {
    const response = await fetch(`${API_BASE_URL}/channels/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: isActive }),
    });
    return handleResponse(response);
  },

  // ==============================================================================
  // ИСПРАВЛЕНИЕ ОШИБКИ `[object Object]`
  // ==============================================================================
  // ЗАМЕНЕНО: Старая версия функции принимала `id: number`. Новая версия
  // принимает один объект и использует деструктуризацию `{ id, body }`.
  // ПОЧЕМУ: Компонент `page.tsx` теперь вызывает эту функцию, передавая ей
  // один сложный объект: `{ id: 123, body: { mode: '...', ... } }`.
  // Старая сигнатура пыталась использовать весь этот объект как ID, что
  // приводило к его преобразованию в строку "[object Object]" в URL.
  // Новая сигнатура правильно "распаковывает" объект, извлекая `id` (число)
  // для URL и `body` (объект) для тела запроса.
  triggerChannelPostsCollection: async ({ id, body }: { id: number; body: PostsCollectionRequestBody }): Promise<{ message: string }> => {
    const response = await fetch(`${API_BASE_URL}/channels/${id}/collect-posts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return handleResponse(response);
  },

  // --- Инсайты ---
  getInsights: async (page = 1, size = 20): Promise<PaginatedInsightsResponse> => {
    const response = await fetch(`${API_BASE_URL}/insights?page=${page}&size=${size}`);
    return handleResponse(response);
  },

  // --- Посты/Данные ---
  getDataPosts: async (params: {
    page?: number;
    size?: number;
    search?: string;
    channelId?: number;
  }): Promise<PaginatedPostsResponse> => {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      size: String(params.size || 10),
      search: params.search || "",
      ...(params.channelId && { channel_id: String(params.channelId) })
    }).toString();
    const response = await fetch(`${API_BASE_URL}/data/posts?${query}`);
    return handleResponse(response);
  },

  getPostDetails: async (postId: number): Promise<PostDetailsData> => {
    const response = await fetch(`${API_BASE_URL}/data/posts/${postId}`);
    return handleResponse(response);
  },
  
  getPostComments: async (params: { 
    postId: number; 
    page?: number; 
    size?: number 
  }): Promise<PaginatedCommentsResponse> => {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      size: String(params.size || 20),
    }).toString();
    const response = await fetch(`${API_BASE_URL}/posts/${params.postId}/comments?${query}`);
    return handleResponse(response);
  },

  // --- Действия с постами ---
  triggerPostAnalysis: async (postId: number): Promise<{ message: string }> => {
    const response = await fetch(`${API_BASE_URL}/posts/${postId}/analyze`, {
        method: 'POST',
    });
    return handleResponse(response);
  },

  triggerPostCommentsCollection: async (params: { postId: number, forceRescan: boolean }): Promise<{ message:string }> => {
    const response = await fetch(`${API_BASE_URL}/posts/${params.postId}/collect-comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_full_rescan: params.forceRescan }),
    });
    return handleResponse(response);
  },

  triggerPostStatsUpdate: async (postId: number): Promise<{ message: string }> => {
    const response = await fetch(`${API_BASE_URL}/posts/${postId}/update-stats`, { 
      method: 'POST' 
    });
    return handleResponse(response);
  },

  // --- Аналитика для Дашбордов ---
  getDynamics: async (startDate: string, endDate: string): Promise<DynamicsDataPoint[]> => {
    const response = await fetch(`${API_BASE_URL}/analytics/dynamics?start_date=${startDate}&end_date=${endDate}`);
    return handleResponse(response);
  },
  
  getSentiment: async (startDate: string, endDate: string): Promise<SentimentDataPoint> => {
    const response = await fetch(`${API_BASE_URL}/analytics/sentiment?start_date=${startDate}&end_date=${endDate}`);
    return handleResponse(response);
  },

  getTopics: async (startDate: string, endDate: string): Promise<TopicDataPoint[]> => {
    const response = await fetch(`${API_BASE_URL}/analytics/topics?start_date=${startDate}&end_date=${endDate}`);
    return handleResponse(response);
  },
};

// --- END OF REVISED FILE frontend/src/lib/api.ts ---