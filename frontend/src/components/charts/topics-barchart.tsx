"use client";
import { BarChart, Card, Title, Subtitle } from "@tremor/react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function TopicsBarChart() {
    const { data, isLoading, error } = useQuery({
        queryKey: ["analyticsTopics"],
        queryFn: api.getTopics,
    });

    if (isLoading) return <p>Загрузка данных...</p>;
    if (error) return <p>Ошибка: {error.message}</p>;

    return (
         <BarChart
            className="mt-6"
            data={data || []}
            index="topic"
            categories={["count"]}
            colors={["blue"]}
            yAxisWidth={150} // Увеличиваем место для длинных названий тем
            layout="vertical"
        />
    );
}