"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { InsightCard } from "@/components/insight-card";

export default function InsightsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["insights"],
    queryFn: () => api.getInsights(1, 50), // Загружаем первые 50 инсайтов
  });

  if (isLoading) return <div>Загрузка инсайтов...</div>;
  if (error) return <div>Ошибка при загрузке: {error.message}</div>;

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold tracking-tight">Лента Инсайтов</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {data?.items.map((insight) => (
          <InsightCard key={insight.post_id} insight={insight} />
        ))}
      </div>
      {/* Здесь в будущем будет пагинация */}
    </div>
  );
}