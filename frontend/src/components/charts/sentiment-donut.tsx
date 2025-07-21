"use client";
import { DonutChart, Card, Title, Legend } from "@tremor/react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function SentimentDonut() {
    const { data, isLoading, error } = useQuery({
        queryKey: ["analyticsSentiment"],
        queryFn: api.getSentiment,
    });

    if (isLoading) return <p>Загрузка данных...</p>;
    if (error) return <p>Ошибка: {error.message}</p>;

    const chartData = [
        { name: "Позитив", value: data?.positive_avg || 0 },
        { name: "Негатив", value: data?.negative_avg || 0 },
        { name: "Нейтрал", value: data?.neutral_avg || 0 },
    ];

    return (
        <>
            <DonutChart
                className="mt-6"
                data={chartData}
                category="value"
                index="name"
                colors={["emerald", "rose", "slate"]}
            />
            <Legend
                className="mt-4"
                categories={["Позитив", "Негатив", "Нейтрал"]}
                colors={["emerald", "rose", "slate"]}
            />
        </>
    );
}