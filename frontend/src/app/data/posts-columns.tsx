// --- START OF FILE frontend/src/app/data/posts-columns.tsx ---

// frontend/src/app/data/posts-columns.tsx

"use client";

import { ColumnDef } from "@tanstack/react-table";
import { PostForTable } from "@/types/data";
import { MoreHorizontal, Bot, Eye, BarChart2, MessageSquarePlus, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";

// Определяем тип для всех действий, которые можно совершить со строкой
type ColumnActions = {
  onViewDetails: (postId: number) => void;
  onAnalyze: (postId: number) => void;
  isAnalyzing: boolean;
  onCollectComments: (postId: number, force: boolean) => void;
  isCollecting: boolean;
  onUpdateStats: (postId: number) => void;
  isUpdating: boolean;
}

// Фабрика для создания колонок. Это позволяет передать в них обработчики с основной страницы.
export const getColumns = (
    actions: ColumnActions
): ColumnDef<PostForTable>[] => [
  {
    accessorKey: "channel_name",
    header: "Канал",
    cell: ({ row }) => (
      <div className="w-[120px] truncate">{row.original.channel_name}</div>
    )
  },
  {
    accessorKey: "text",
    header: "Текст поста",
    cell: ({ row }) => {
        const text = row.original.text;
        const shortText = text ? text.substring(0, 100) + (text.length > 100 ? "..." : "") : "Нет текста";
        
        // Делаем ячейку с текстом кликабельной для открытия деталей
        return (
          <div 
            className="max-w-[450px] truncate cursor-pointer hover:underline"
            onClick={() => actions.onViewDetails(row.original.id)}
            title={text} // Показываем полный текст при наведении
          >
            {shortText}
          </div>
        );
    }
  },
  { accessorKey: "comments_count", header: "Комм." },
  { accessorKey: "views_count", header: "Просм." },
  {
    accessorKey: "has_analysis",
    header: "Анализ",
    cell: ({ row }) => (
      <div className="flex justify-center">
        {row.original.has_analysis 
            ? <Badge variant="secondary" className="text-green-400 border-green-400/30"><Bot className="h-4 w-4" /></Badge> 
            : <Badge variant="outline" className="text-muted-foreground">Нет</Badge>
        }
      </div>
    )
  },
  {
    accessorKey: "created_at",
    header: "Дата",
    cell: ({ row }) => new Date(row.original.created_at).toLocaleDateString('ru-RU'),
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const post = row.original;
      const isAnyActionPending = actions.isAnalyzing || actions.isCollecting || actions.isUpdating;

      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-8 w-8 p-0">
              <span className="sr-only">Открыть меню</span>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Действия</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => actions.onViewDetails(post.id)}>
              <Eye className="mr-2 h-4 w-4" />
              Просмотреть детали
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
                onClick={() => actions.onCollectComments(post.id, false)}
                disabled={isAnyActionPending}
            >
              <MessageSquarePlus className="mr-2 h-4 w-4" />
              Собрать/добрать комм.
            </DropdownMenuItem>
            <DropdownMenuItem
                onClick={() => actions.onUpdateStats(post.id)}
                disabled={isAnyActionPending}
            >
              <BarChart2 className="mr-2 h-4 w-4" />
              Обновить статистику
            </DropdownMenuItem>
             <DropdownMenuItem
                onClick={() => actions.onAnalyze(post.id)}
                disabled={isAnyActionPending || post.has_analysis} // Блокируем, если анализ уже есть
            >
              <Bot className="mr-2 h-4 w-4" />
              Запросить AI-анализ
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
                className="text-amber-500 focus:text-amber-400 focus:bg-amber-950"
                onClick={() => confirm("Вы уверены, что хотите полностью пересобрать комментарии? Это может занять много времени.") && actions.onCollectComments(post.id, true)}
                disabled={isAnyActionPending}
            >
              <RefreshCcw className="mr-2 h-4 w-4" />
              Полностью пересобрать
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );
    },
  },
];
// --- END OF FILE frontend/src/app/data/posts-columns.tsx ---