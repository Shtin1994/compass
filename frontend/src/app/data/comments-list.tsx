// frontend/src/app/data/comments-list.tsx

"use client";

import React, { useEffect, Fragment } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useInView } from "react-intersection-observer";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { MessageSquareWarning, MessageCircleOff } from "lucide-react";
import { Comment } from "@/types/data";

// Компонент для отображения одного комментария
const CommentItem = ({ comment }: { comment: Comment }) => (
    <div className="p-3 rounded-lg border bg-card text-sm">
        <div className="flex justify-between items-center mb-1">
            <p className="font-semibold text-sm">{comment.author_name || "Аноним"}</p>
            <p className="text-xs text-muted-foreground">
                {new Date(comment.created_at).toLocaleString('ru-RU')}
            </p>
        </div>
        <p className="break-words whitespace-pre-wrap">{comment.text}</p>
    </div>
);

// Скелет для загрузки
const CommentSkeleton = () => (
    <div className="p-3 rounded-lg border">
        <div className="flex justify-between items-center mb-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/4" />
        </div>
        <Skeleton className="h-4 w-full mb-1" />
        <Skeleton className="h-4 w-5/6" />
    </div>
);

export function CommentsList({ postId }: { postId: number | null }) {
    // Хук для отслеживания видимости элемента. Когда ref появится в экране, inView станет true
    const { ref, inView } = useInView({ threshold: 0.5 });

    const {
        data,
        error,
        isLoading,
        hasNextPage,
        fetchNextPage,
        isFetchingNextPage,
    } = useInfiniteQuery({
        queryKey: ["postComments", postId],
        queryFn: ({ pageParam = 1 }) =>
            api.getPostComments({ postId: postId!, page: pageParam, size: 20 }),
        initialPageParam: 1,
        // ИСПРАВЛЕННАЯ ЛОГИКА
        getNextPageParam: (lastPage, allPages) => {
            if (lastPage.items.length > 0) {
                const loadedItems = allPages.reduce((acc, page) => acc + page.items.length, 0);
                if (loadedItems < lastPage.total) {
                    return allPages.length + 1; // Вот исправленная строка
                }
            }
            return undefined; // Больше страниц нет
        },
        enabled: !!postId,
    });

    // Эффект, который подгружает данные, когда триггер-элемент становится видимым
    useEffect(() => {
        if (inView && hasNextPage && !isFetchingNextPage) {
            fetchNextPage();
        }
    }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

    if (!postId) return null;

    if (isLoading) {
        return (
            <div className="space-y-4 mt-4">
                {[...Array(5)].map((_, i) => <CommentSkeleton key={i} />)}
            </div>
        );
    }

    if (error) {
        return (
            <Alert variant="destructive" className="mt-4">
                <MessageSquareWarning className="h-4 w-4" />
                <AlertTitle>Ошибка загрузки</AlertTitle>
                <AlertDescription>Не удалось загрузить комментарии.</AlertDescription>
            </Alert>
        );
    }
    
    const allComments = data?.pages.flatMap(page => page.items) ?? [];
    
    if (allComments.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center text-center text-muted-foreground p-8 h-full">
            <MessageCircleOff className="h-12 w-12 mb-4" />
            <p className="font-semibold">Комментариев пока нет</p>
            <p className="text-sm">К этому посту еще не оставили комментариев.</p>
        </div>
      );
    }

    return (
        <div className="space-y-4">
            {data?.pages.map((page, i) => (
                <Fragment key={i}>
                    {page.items.map((comment) => (
                        <CommentItem key={comment.id} comment={comment} />
                    ))}
                </Fragment>
            ))}

            {/* Элемент-триггер для загрузки */}
            <div ref={ref} className="h-10 w-full mt-4">
                {isFetchingNextPage && <CommentSkeleton />}
                {!hasNextPage && allComments.length > 0 && (
                    <p className="text-center text-xs text-muted-foreground pt-4">Все комментарии загружены</p>
                )}
            </div>
        </div>
    );
}