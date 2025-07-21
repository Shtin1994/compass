"use client";
import { AreaChart, Card, Title } from "@tremor/react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function DynamicsChart() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["analyticsDynamics"],
    queryFn: api.getDynamics,
  });

  if (isLoading) return <p>Загрузка данных...</p>;
  if (error) return <p>Ошибка: {error.message}</p>;

  return (
    <AreaChart
      className="h-72 mt-4"
      data={data || []}
      index="date"
      categories={["posts", "comments"]}
      colors={["indigo", "cyan"]}
      yAxisWidth={30}
    />
  );
}