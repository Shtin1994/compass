// --- START OF FILE frontend/src/app/data/page.tsx ---

// frontend/src/app/data/page.tsx

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DataTable } from "@/components/ui/data-table";
import { getColumns } from "./posts-columns";
import { useEffect, useMemo, useState } from "react";
import { PaginationState } from "@tanstack/react-table";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/use-debounce";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { PostDetails } from "./post-details";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Channel } from "@/types/channel";
import { Toaster, toast } from 'sonner';

export default function DataPage() {
  const queryClient = useQueryClient();

  // Состояния для управления UI
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 10 });
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedChannel, setSelectedChannel] = useState<string>("all");
  const [selectedPostId, setSelectedPostId] = useState<number | null>(null);

  const debouncedSearchTerm = useDebounce(searchTerm, 400);

  // Запрос списка каналов для выпадающего списка
  const { data: channelsData } = useQuery<Channel[]>({
    queryKey: ["channels"],
    queryFn: api.getChannels,
    staleTime: 5 * 60 * 1000, // Каналы не меняются часто, кешируем на 5 минут
  });
  
  // Сбрасываем пагинацию на первую страницу при смене фильтров
  useEffect(() => {
    setPagination(p => ({ ...p, pageIndex: 0 }));
  }, [debouncedSearchTerm, selectedChannel]);

  // Основной запрос данных для таблицы с учетом всех фильтров и пагинации
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["dataPosts", pagination, debouncedSearchTerm, selectedChannel],
    queryFn: () => api.getDataPosts({
      page: pagination.pageIndex + 1,
      size: pagination.pageSize,
      search: debouncedSearchTerm,
      channelId: selectedChannel === "all" ? undefined : Number(selectedChannel),
    }),
    keepPreviousData: true,
  });
  
  // Общий обработчик успеха для всех мутаций
  const onActionSuccess = (response: { message: string }) => {
    toast.success(response.message || "Задача успешно поставлена в очередь!");
    // Инвалидируем запросы, чтобы обновить данные в таблице и в открытой боковой панели
    queryClient.invalidateQueries({ queryKey: ["dataPosts"] });
    if (selectedPostId) {
      queryClient.invalidateQueries({ queryKey: ["postDetails", selectedPostId] });
    }
  };

  // Общий обработчик ошибок для всех мутаций
  const onActionError = (error: Error, defaultMessage: string) => {
    toast.error(`${defaultMessage}: ${error.message}`);
  };

  // Мутация для запуска сбора комментариев
  const collectCommentsMutation = useMutation({
    mutationFn: api.triggerPostCommentsCollection,
    onSuccess: onActionSuccess,
    onError: (error: Error) => onActionError(error, "Ошибка сбора комментариев"),
  });

  // Мутация для обновления статистики
  const updateStatsMutation = useMutation({
    mutationFn: api.triggerPostStatsUpdate,
    onSuccess: onActionSuccess,
    onError: (error: Error) => onActionError(error, "Ошибка обновления статистики"),
  });

  // Мутация для запуска анализа поста
  const analyzeMutation = useMutation({
    mutationFn: api.triggerPostAnalysis,
    onSuccess: onActionSuccess,
    onError: (error: Error) => onActionError(error, "Ошибка запуска анализа"),
  });

  // Создаем колонки с помощью useMemo, чтобы они не пересоздавались на каждый рендер.
  // Передаем им все необходимые обработчики и состояния.
  const columns = useMemo(() => getColumns({
    onViewDetails: (postId) => setSelectedPostId(postId),
    onAnalyze: (postId) => analyzeMutation.mutate(postId),
    isAnalyzing: analyzeMutation.isPending,
    onCollectComments: (postId, force) => collectCommentsMutation.mutate({ postId, forceRescan: force }),
    isCollecting: collectCommentsMutation.isPending,
    onUpdateStats: (postId) => updateStatsMutation.mutate(postId),
    isUpdating: updateStatsMutation.isPending,
  }), [analyzeMutation.isPending, collectCommentsMutation.isPending, updateStatsMutation.isPending]);

  const pageCount = data ? Math.ceil(data.total / data.size) : 0;
  
  // Определяем, находится ли таблица в состоянии загрузки (первичной или фоновой)
  const isTableLoading = isLoading || isFetching;

  return (
    <>
      <Toaster richColors position="top-right" />
      <div className="h-full flex flex-col space-y-4">
        <h2 className="text-2xl font-bold tracking-tight">Собранные Данные</h2>
        
        {/* Панель фильтров */}
        <div className="flex items-center space-x-4">
          <Input
            placeholder="Поиск по тексту поста..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
          <Select value={selectedChannel} onValueChange={setSelectedChannel}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Все каналы" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все каналы</SelectItem>
              {channelsData?.map(channel => (
                <SelectItem key={channel.id} value={String(channel.id)}>
                  {channel.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Таблица занимает все оставшееся место */}
        <div className="flex-grow">
            <DataTable
              columns={columns}
              data={data?.items ?? []}
              isLoading={isTableLoading}
              totalCount={data?.total ?? 0}
              pageCount={pageCount}
              pageIndex={pagination.pageIndex}
              pageSize={pagination.pageSize}
              onPaginationChange={setPagination}
            />
        </div>
      </div>

      {/* Боковая панель для деталей поста */}
      <Sheet open={!!selectedPostId} onOpenChange={(isOpen) => !isOpen && setSelectedPostId(null)}>
        <SheetContent className="w-[500px] sm:w-[500px] sm:max-w-none">
          <SheetHeader>
            <SheetTitle>Детали Поста</SheetTitle>
          </SheetHeader>
          {/* Передаем ID в PostDetails, он будет загружать свои данные сам */}
          <PostDetails postId={selectedPostId} />
        </SheetContent>
      </Sheet>
    </>
  );
}
// --- END OF FILE frontend/src/app/data/page.tsx ---