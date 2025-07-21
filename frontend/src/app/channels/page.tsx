"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api, queryClient } from "@/lib/api";
import { Channel } from "@/types/channel";
import { MoreHorizontal, PlusCircle, RefreshCw } from "lucide-react";

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
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge"; // Добавим Badge для статуса

// Устанавливаем компонент Badge, если его еще нет
// npx shadcn@latest add badge

export default function ChannelsPage() {
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newChannelUsername, setNewChannelUsername] = useState("");

  // --- Запросы к API с помощью TanStack Query ---

  // 1. Получение списка каналов
  const { data: channels = [], isLoading, error } = useQuery<Channel[]>({
    queryKey: ["channels"],
    queryFn: api.getChannels,
  });

  // 2. Мутация для добавления канала
  const addChannelMutation = useMutation({
    mutationFn: api.addChannel,
    onSuccess: () => {
      // При успехе - аннулируем кэш запроса "channels",
      // чтобы React Query автоматически запросил свежие данные
      queryClient.invalidateQueries({ queryKey: ["channels"] });
      setIsAddDialogOpen(false);
      setNewChannelUsername("");
      // TODO: Добавить красивое уведомление (toast)
    },
    onError: (error) => {
      alert(`Ошибка: ${error.message}`); // Простая обработка ошибок
    }
  });

  // 3. Мутация для изменения статуса
  const updateStatusMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) =>
      api.updateChannelStatus(id, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["channels"] });
    },
  });

  // 4. Мутация для запуска сбора
  const triggerCollectionMutation = useMutation({
    mutationFn: api.triggerCollection,
    onSuccess: () => {
        // TODO: Показать уведомление "Задача запущена"
        alert("Задача по сбору данных запущена в фоновом режиме!");
    },
    onError: (error) => {
        alert(`Ошибка: ${error.message}`);
    }
  });

  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div>Ошибка при загрузке каналов: {error.message}</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Каналы Мониторинга</h2>
        <Button onClick={() => setIsAddDialogOpen(true)}>
          <PlusCircle className="mr-2 h-4 w-4" />
          Добавить канал
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
                <TableCell>
                  <Badge variant={channel.is_active ? "default" : "outline"}>
                    {channel.is_active ? "Активен" : "Неактивен"}
                  </Badge>
                </TableCell>
                <TableCell className="font-medium">{channel.name}</TableCell>
                <TableCell>{channel.telegram_id}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" className="h-8 w-8 p-0">
                        <span className="sr-only">Открыть меню</span>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => triggerCollectionMutation.mutate(channel.id)}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Запустить сбор
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => updateStatusMutation.mutate({ id: channel.id, isActive: !channel.is_active })}>
                        <Switch className="mr-2 h-4 w-4" checked={channel.is_active} readOnly/>
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
      
      {/* Диалоговое окно для добавления канала */}
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
              <Label htmlFor="username" className="text-right">
                Username
              </Label>
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
              {addChannelMutation.isPending ? "Добавление..." : "Добавить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}