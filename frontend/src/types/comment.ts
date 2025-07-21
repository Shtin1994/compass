// --- START OF FILE frontend/src/types/comment.ts ---

export interface Comment {
  id: number;
  text: string;
  author_name: string | null;
  created_at: string; // Даты приходят с бэкенда как строки в формате ISO
}

// --- END OF FILE frontend/src/types/comment.ts ---