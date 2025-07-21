// --- START OF FILE frontend/src/app/data/comments-list.tsx ---

// frontend/src/app/data/comments-list.tsx

"use client";

import React from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { MessageSquareWarning, MessageCircleOff, Loader2 } from "lucide-react";
import { Comment } from "@/types/comment";
import { Button } from "@/components/ui/button";

/**
 * Компонент для отображения списка комментариев к посту.
 * Использует useInfiniteQuery для загрузки данных с пагинацией ("загрузить еще").
 * @param {object} props - Пропсы компонента.
 * @param {number} props.postId - ID поста, для которого нужно загрузить комментарии.
 */
export function CommentsList({ postId }: { postId: number }) {
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isLoading,
    isFetchingNextPage,
  } = useInfiniteQuery<{ items: Comment[], has_next: boolean, page: number }>({
    queryKey: ["postComments", postId],
    queryFn: ({ pageParam = 1 }) =>
      api.getPostComments({ postId, page: pageParam, size: 20 }),
    // ВНИМАНИЕ: Эта функция - ключ к работе пагинации.
    // Она определяет, есть ли следующая страница, на основе ответа от API.
    getNextPageParam: (lastPage, allPages) => {
      // Чтобы кнопка "Загрузить еще" появилась, ваш API ДОЛЖЕН вернуть в ответе
      // поле `has_next: true`, когда есть еще комментарии для загрузки.
      // Если `lastPage.has_next` равно false или undefined, `hasNextPage` станет false,
      // и кнопка не отобразится.
      //
      // ПРОВЕРЬТЕ ОТВЕТ ВАШЕГО API! Он должен выглядеть примерно так:
      // { items: [...], page: 1, has_next: true }
      if (lastPage.has_next) {
        return lastPage.page + 1;
      }
      return undefined;
    },
    enabled: !!postId,
    initialPageParam: 1,
  });

  if (isLoading) {
    return <CommentsSkeleton />;
  }

  if (error) {
    return (
      <Alert variant="destructive" className="mt-4">
        <MessageSquareWarning className="h-4 w-4" />
        <AlertTitle>Ошибка загрузки</AlertTitle>
        <AlertDescription>
          Не удалось загрузить комментарии. Попробуйте позже.
        </AlertDescription>
      </Alert>
    );
  }
  
  const allComments = data?.pages.flatMap(page => page.items) || [];

  if (allComments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center text-muted-foreground p-8 h-full">
        <MessageCircleOff className="h-12 w-12 mb-4" />
        <p className="font-semibold">Комментарии отсутствуют</p>
        <p className="text-sm">К этому посту еще не оставили комментариев.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {data.pages.map((group, i) => (
        <React.Fragment key={i}>
          {group.items.map((comment) => (
            <div key={comment.id} className="p-3 rounded-lg border bg-card">
              <div className="flex justify-between items-center mb-1">
                <p className="font-semibold text-sm">{comment.author_name || "Аноним"}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(comment.created_at).toLocaleString("ru-RU")}
                </p>
              </div>
              <p className="text-sm whitespace-pre-wrap break-words">{comment.text}</p>
            </div>
          ))}
        </React.Fragment>
      ))}

      <div className="flex justify-center pt-4">
        {hasNextPage && (
          <Button
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            variant="outline"
          >
            {isFetchingNextPage ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Загрузка...
              </>
            ) : (
              "Загрузить еще"
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

// Скелет для состояния загрузки списка комментариев (без изменений)
const CommentsSkeleton = () => (
    <div className="space-y-4 mt-4">
        {[...Array(5)].map((_, i) => (
            <div key={i} className="p-3 rounded-lg border">
                <div className="flex justify-between items-center mb-2">
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-3 w-1/4" />
                </div>
                <Skeleton className="h-4 w-full mb-1" />
                <Skeleton className="h-4 w-5/6" />
            </div>
        ))}
    </div>
);