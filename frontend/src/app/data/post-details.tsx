// --- START OF FILE frontend/src/app/data/post-details.tsx ---

// frontend/src/app/data/post-details.tsx

"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Terminal } from "lucide-react";
import React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CommentsList } from "./comments-list"; 
import ReactMarkdown from 'react-markdown';

export function PostDetails({ postId }: { postId: number | null }) {
  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["postDetails", postId],
    queryFn: () => api.getPostDetails(postId!),
    enabled: !!postId,
  });

  if (!postId) return null;

  if (isLoading) {
    return <PostDetailsSkeleton />;
  }
  
  if (error) {
     return (
        <Alert variant="destructive" className="m-4">
            <Terminal className="h-4 w-4" />
            <AlertTitle>Ошибка</AlertTitle>
            <AlertDescription>
              Не удалось загрузить детали поста. {/* @ts-ignore */}
              {error.message}
            </AlertDescription>
        </Alert>
     );
  }

  if (!data) return null;

  const prepareMarkdown = (text: string) => {
    if (!text) return "";
    return text.replace(/\*\* \*\*/g, "**\n\n**");
  };

  return (
    <div className={`pt-4 flex flex-col h-full ${isFetching ? 'opacity-50' : 'opacity-100'} transition-opacity`}>
      <div className="px-4 pb-2 shrink-0">
        <h3 className="font-semibold text-lg break-words">Пост #{data.telegram_id} из "{data.channel_name}"</h3>
        <p className="text-sm text-muted-foreground">
          Опубликовано: {new Date(data.created_at).toLocaleString('ru-RU')}
        </p>
      </div>
      
      <Tabs defaultValue="analysis" className="w-full flex flex-col flex-1 min-h-0">
        <TabsList className="grid w-full grid-cols-2 mx-4 my-2 shrink-0">
            <TabsTrigger value="analysis">Анализ</TabsTrigger>
            <TabsTrigger value="comments" disabled={data.comments_count === 0}>
                Комментарии ({data.comments_count.toLocaleString('ru-RU')})
            </TabsTrigger>
        </TabsList>
        
        <TabsContent value="analysis" className="flex-1 min-h-0">
            <div className="h-full overflow-y-auto px-4">
                <div className="space-y-6 pt-2">
                    {data.text && (
                        <div className="rounded-md border p-4 bg-background/50 prose prose-sm dark:prose-invert max-w-none break-words">
                            <ReactMarkdown>
                                {prepareMarkdown(data.text)}
                            </ReactMarkdown>
                        </div>
                    )}

                    <div>
                      <h4 className="font-semibold mb-2">Статистика</h4>
                      {/* Убедимся, что здесь тоже есть flex-wrap */}
                      <div className="flex flex-wrap gap-2">
                          <Badge variant="secondary">Просмотры: {data.views_count.toLocaleString('ru-RU')}</Badge>
                          <Badge variant="secondary">Комментарии: {data.comments_count.toLocaleString('ru-RU')}</Badge>
                          {data.reactions && Object.entries(data.reactions).map(([emoji, count]) => (
                            <Badge key={emoji} variant="outline" className="flex items-center gap-1.5">
                              <span>{emoji}</span>
                              <span className="text-xs font-mono">{typeof count === 'number' ? count.toLocaleString('ru-RU') : count}</span>
                            </Badge>
                          ))}
                      </div>
                    </div>
                    
                    {data.analysis ? (
                      <div className="space-y-3">
                        <h4 className="font-semibold">Анализ от AI ({data.analysis.model_used})</h4>
                        <Alert>
                          <Terminal className="h-4 w-4" />
                          <AlertTitle>Ключевая мысль</AlertTitle>
                          <AlertDescription className="pt-2 break-words">
                            {data.analysis.summary}
                          </AlertDescription>
                        </Alert>
                         <div>
                            <h5 className="font-medium mb-2 text-sm">Темы</h5>
                            {/* ИСПРАВЛЕНИЕ: Добавляем 'flex' и 'flex-wrap' для переноса бейджей */}
                            <div className="flex flex-wrap gap-2">
                                {data.analysis.key_topics?.map((topic, index) => (
                                    <Badge key={`${topic}-${index}`} variant="outline">{topic}</Badge>
                                ))}
                            </div>
                         </div>
                         <div>
                            <h5 className="font-medium mb-2 text-sm">Тональность</h5>
                            {/* ИСПРАВЛЕНИЕ: Добавляем 'flex' и 'flex-wrap' и сюда для консистентности */}
                            <div className="flex flex-wrap gap-2">
                                <Badge className="bg-green-700/80 hover:bg-green-700">Позитив: {data.analysis.sentiment.positive_percent}%</Badge>
                                <Badge className="bg-red-700/80 hover:bg-red-700">Негатив: {data.analysis.sentiment.negative_percent}%</Badge>
                                <Badge variant="secondary">Нейтральность: {data.analysis.sentiment.neutral_percent}%</Badge>
                            </div>
                         </div>
                      </div>
                    ) : (
                         <Alert variant="default" className="mt-4">
                            <Terminal className="h-4 w-4" />
                            <AlertTitle>AI-анализ отсутствует</AlertTitle>
                            <AlertDescription>
                              Запросите анализ через меню действий в таблице, чтобы увидеть здесь результат.
                            </AlertDescription>
                        </Alert>
                    )}
                </div>
            </div>
        </TabsContent>

        <TabsContent value="comments" className="flex-1 min-h-0">
             <div className="h-full overflow-y-auto px-4">
                <CommentsList postId={postId} />
             </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Скелет без изменений
const PostDetailsSkeleton = () => (
  <div className="space-y-6 p-4">
    {/* ... ваш код скелета ... */}
  </div>
);