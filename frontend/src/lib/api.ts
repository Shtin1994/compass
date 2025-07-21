// --- START OF FILE frontend/src/lib/api.ts ---

import { QueryClient } from '@tanstack/react-query';
import { Channel } from '@/types/channel';
import { PaginatedInsightsResponse } from '@/types/insight';
import { DynamicsDataPoint, SentimentDataPoint, TopicDataPoint } from '@/types/analytics';
import { PostDetailsData, PaginatedPostsResponse } from '@/types/data';
// ИЗМЕНЕНИЕ: Добавлен импорт типа для комментария
import { Comment } from '@/types/comment';

// Убеждаемся, что переменная окружения доступна
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
if (!API_BASE_URL) {
    throw new Error("Переменная окружения NEXT_PUBLIC_API_BASE_URL не установлена!");
}

export const queryClient = new QueryClient();

/**
 * Общая функция-обработчик ответа от API.
 * @param response - Объект Response от fetch.
 * @returns - Данные в формате JSON или объект с сообщением.
 * @throws {Error} - Выбрасывает ошибку с текстом из ответа API, если запрос неуспешен.
 */
const handleResponse = async (response: Response) => {
  // Пытаемся получить детали ошибки из тела ответа в любом случае
  const responseBody = await response.json().catch(() => ({ detail: response.statusText }));

  if (!response.ok) {
    // Создаем осмысленное сообщение об ошибке
    const errorMessage = responseBody.detail || `Произошла ошибка, статус: ${response.status}`;
    throw new Error(errorMessage);
  }

  // Для успешных ответов (включая 202 Accepted) возвращаем тело, т.к. бэкенд шлет { message: "..." }
  return responseBody;
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

  triggerCollection: async (id: number): Promise<{ message: string }> => {
    const response = await fetch(`${API_BASE_URL}/channels/${id}/collect`, {
      method: 'POST',
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
  
  // НОВАЯ ФУНКЦИЯ: Загрузка комментариев для поста
  getPostComments: async (params: { 
    postId: number; 
    page?: number; 
    size?: number 
  }): Promise<{ items: Comment[] }> => {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      size: String(params.size || 20),
    }).toString();
    // Эндпоинт, который мы ранее создали на бэкенде
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
// --- END OF FILE frontend/src/lib/api.ts ---