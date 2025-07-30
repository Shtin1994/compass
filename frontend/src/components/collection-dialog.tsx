// --- Создайте новый файл frontend/src/components/collection-dialog.tsx ---
"use client";

import { useState } from "react";
import { format } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

import { Channel } from "@/types/channel";
import { PostsCollectionRequestBody } from "@/lib/api";

// Определяем типы для пропсов компонента
interface CollectionDialogProps {
  channel: Channel | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (body: PostsCollectionRequestBody) => void;
  isPending: boolean;
}

// Тип для нашего Enum с бэкенда
type CollectionMode = "get_new" | "historical" | "initial";

export function CollectionDialog({ channel, isOpen, onClose, onSubmit, isPending }: CollectionDialogProps) {
  const [mode, setMode] = useState<CollectionMode>("get_new");
  const [dateFrom, setDateFrom] = useState<Date | undefined>();
  const [dateTo, setDateTo] = useState<Date | undefined>();
  const [limit, setLimit] = useState<number>(100);

  const handleSubmit = () => {
    const body: PostsCollectionRequestBody = {
      mode,
      date_from: mode === 'historical' && dateFrom ? format(dateFrom, "yyyy-MM-dd") : null,
      date_to: mode === 'historical' && dateTo ? format(dateTo, "yyyy-MM-dd") : null,
      limit: (mode === 'historical' || mode === 'initial') ? limit : null,
    };
    onSubmit(body);
  };

  if (!channel) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Запустить сбор для "{channel.name}"</DialogTitle>
          <DialogDescription>
            Выберите режим и укажите параметры для сбора постов.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <RadioGroup value={mode} onValueChange={(value: CollectionMode) => setMode(value)}>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="get_new" id="r1" />
              <Label htmlFor="r1">Собрать новые посты</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="initial" id="r2" />
              <Label htmlFor="r2">Первичная загрузка</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="historical" id="r3" />
              <Label htmlFor="r3">Собрать за период (исторический)</Label>
            </div>
          </RadioGroup>

          {/* Контекстные поля */}
          {mode === "initial" && (
            <div className="grid gap-2">
              <Label htmlFor="limit">Лимит постов</Label>
              <Input id="limit" type="number" value={limit} onChange={e => setLimit(Number(e.target.value))} />
            </div>
          )}

          {mode === "historical" && (
            <div className="grid grid-cols-2 gap-4">
               <div className="grid gap-2">
                  <Label>Начальная дата</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant={"outline"} className={cn("justify-start text-left font-normal", !dateFrom && "text-muted-foreground")}>
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateFrom ? format(dateFrom, "PPP") : <span>Выберите дату</span>}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0"><Calendar mode="single" selected={dateFrom} onSelect={setDateFrom} initialFocus/></PopoverContent>
                  </Popover>
               </div>
                <div className="grid gap-2">
                  <Label>Конечная дата</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant={"outline"} className={cn("justify-start text-left font-normal", !dateTo && "text-muted-foreground")}>
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {dateTo ? format(dateTo, "PPP") : <span>Выберите дату</span>}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0"><Calendar mode="single" selected={dateTo} onSelect={setDateTo} /></PopoverContent>
                  </Popover>
                </div>
                <div className="grid gap-2 col-span-2">
                  <Label htmlFor="limit-hist">Лимит постов</Label>
                  <Input id="limit-hist" type="number" value={limit} onChange={e => setLimit(Number(e.target.value))} />
                </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button onClick={handleSubmit} disabled={isPending}>
            {isPending ? "Запуск..." : "Запустить"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}