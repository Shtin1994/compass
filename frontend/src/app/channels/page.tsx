// --- START OF FILE frontend/src/app/channels/page.tsx ---

"use client";

// ==============================================================================
// КОММЕНТАРИЙ ДЛЯ ПРОГРАММИСТА:
// Этот файл — основная страница для управления каналами.
// Его задачи:
// 1. Отображать список каналов, полученных с бэкенда.
// 2. Предоставлять UI для добавления, активации/деактивации каналов.
// 3. Управлять состоянием модальных окон (добавления и запуска сбора).
// 4. Инициировать API-запросы (мутации) и обрабатывать их состояния (загрузка, успех, ошибка).
// ==============================================================================

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
// ДОБАВЛЕНО: Импортируем наш новый тип для тела запроса
import { api, queryClient, PostsCollectionRequestBody } from "@/lib/api";
import { Channel } from "@/types/channel";
import { MoreHorizontal, PlusCircle, RefreshCw, Loader2 } from "lucide-react";
import { toast } from "sonner"; // Для красивых уведомлений

// Импортируем наши UI компоненты
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
// ДОБАВЛЕНО: Импортируем наш новый, переиспользуемый компонент-диалог
import { CollectionDialog } from "@/components/collection-dialog";

export default function ChannelsPage() {
  // Состояние для диалога добавления канала
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newChannelUsername, setNewChannelUsername] = useState("");

  // ДОБАВЛЕНО: Состояние для диалога сбора постов.
  // ПОЧЕМУ: Это элегантный способ управлять и состоянием открытия диалога, и передачей
  // в него данных. Если `collectionTarget` равен `null` - диалог закрыт. Если в нем
  // объект `Channel` - диалог открыт и имеет доступ к данным этого канала.
  const [collectionTarget, setCollectionTarget] = useState<Channel | null>(null);

  // --- Запросы к API с помощью TanStack Query ---

  // 1. Получение списка каналов (без изменений)
  const { data: channels = [], isLoading, error } = useQuery<Channel[]>({
    queryKey: ["channels"],
    queryFn: api.getChannels,
  });

  // 2. Мутация для добавления канала (без изменений)
  const addChannelMutation = useMutation({
    mutationFn: api.addChannel,
    onSuccess: (newChannel) => {
      toast.success(`Канал "${newChannel.name}" успешно добавлен!`);
      queryClient.invalidateQueries({ queryKey: ["channels"] });
      setIsAddDialogOpen(false);
      setNewChannelUsername("");
    },
    onError: (error) => toast.error(`Ошибка добавления: ${error.message}`),
  });

  // 3. Мутация для изменения статуса (без изменений)
  const updateStatusMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) =>
      api.updateChannelStatus(id, isActive),
    onSuccess: (updatedChannel) => {
      toast.info(`Статус канала "${updatedChannel.name}" изменен.`);
      queryClient.invalidateQueries({ queryKey: ["channels"] });
    },
    onError: (error) => toast.error(`Ошибка обновления: ${error.message}`),
  });

  // 4. ИЗМЕНЕНО: Мутация для запуска сбора.
  // ПОЧЕМУ: Теперь она полностью соответствует обновленному методу в `api.ts`.
  // Она ожидает объект, содержащий `id` канала и `body` с параметрами сбора.
  const triggerCollectionMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: PostsCollectionRequestBody }) =>
      api.triggerChannelPostsCollection({ id, body }),
    onSuccess: (data) => {
        toast.info(data.message || "Задача по сбору данных запущена.");
        setCollectionTarget(null); // Закрываем диалог при успешном запуске
    },
    onError: (error) => toast.error(`Ошибка запуска сбора: ${error.message}`),
  });

  // --- Обработчики действий пользователя ---

  // Этот обработчик открывает диалог сбора для конкретного канала
  const handleOpenCollectionDialog = (channel: Channel) => {
    setCollectionTarget(channel);
  };

  // Этот обработчик вызывается ИЗ диалога, когда пользователь нажимает "Запустить"
  const handleTriggerCollection = (body: PostsCollectionRequestBody) => {
    // Проверка, что у нас есть целевой канал (на всякий случай)
    if (!collectionTarget) return;
    // Запускаем мутацию, передавая ID целевого канала и тело запроса из формы
    triggerCollectionMutation.mutate({ id: collectionTarget.id, body });
  };


  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div>Ошибка при загрузке каналов: {error.message}</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Каналы Мониторинга</h2>
        <Button onClick={() => setIsAddDialogOpen(true)}>
          <PlusCircle className="mr-2 h-4 w-4" /> Добавить канал
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Статус</TableHead>
              <TableHead>Название канала</TableHead>
              <TableHead>Telegram ID</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {channels.map((channel) => (
              <TableRow key={channel.id}>
                <TableCell><Badge variant={channel.is_active ? "default" : "secondary"}>{channel.is_active ? "Активен" : "Неактивен"}</Badge></TableCell>
                <TableCell className="font-medium">{channel.name}</TableCell>
                <TableCell>{String(channel.telegram_id)}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" className="h-8 w-8 p-0" disabled={triggerCollectionMutation.isPending && triggerCollectionMutation.variables?.id === channel.id}>
                          {triggerCollectionMutation.isPending && triggerCollectionMutation.variables?.id === channel.id ? <Loader2 className="h-4 w-4 animate-spin"/> : <MoreHorizontal className="h-4 w-4" />}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {/* ИЗМЕНЕНО: onClick теперь открывает диалог, а не запускает мутацию напрямую */}
                      {/* Троеточие в названии - хороший UX, намекающий что будет еще одно действие. */}
                      <DropdownMenuItem onClick={() => handleOpenCollectionDialog(channel)}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Запустить сбор...
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => updateStatusMutation.mutate({ id: channel.id, isActive: !channel.is_active })} disabled={updateStatusMutation.isPending}>
                        <div className="mr-2 h-4 w-4"/>
                        {channel.is_active ? "Деактивировать" : "Активировать"}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      
      {/* Диалоговое окно для добавления канала (остается без изменений) */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Добавить новый канал</DialogTitle>
            <DialogDescription>
              Введите публичный username канала (без @). Система проверит его доступность.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="username" className="text-right">Username</Label>
              <Input
                id="username"
                value={newChannelUsername}
                onChange={(e) => setNewChannelUsername(e.target.value)}
                className="col-span-3"
                placeholder="например, durov"
              />
            </div>
          </div>
          <DialogFooter>
            <Button 
              type="submit" 
              onClick={() => addChannelMutation.mutate(newChannelUsername)}
              disabled={addChannelMutation.isPending}
            >
              {addChannelMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {addChannelMutation.isPending ? "Добавление..." : "Добавить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ДОБАВЛЕНО: Наше новое диалоговое окно для настроек сбора. */}
      {/* Оно рендерится здесь, а управляется через props, которые мы передаем из состояния страницы. */}
      <CollectionDialog
        channel={collectionTarget}
        isOpen={!!collectionTarget}
        onClose={() => setCollectionTarget(null)}
        onSubmit={handleTriggerCollection}
        isPending={triggerCollectionMutation.isPending}
      />
    </div>
  );
}
// --- END OF FILE frontend/src/app/channels/page.tsx ---