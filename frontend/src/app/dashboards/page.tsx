import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DynamicsChart } from "@/components/charts/dynamics-chart";
import { SentimentDonut } from "@/components/charts/sentiment-donut";
import { TopicsBarChart } from "@/components/charts/topics-barchart";

export default function DashboardsPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold tracking-tight">Дашборды Анализа</h2>
      {/* Здесь в будущем будут фильтры */}
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Динамика постов и комментариев (30 дней)</CardTitle>
          </CardHeader>
          <CardContent>
            <DynamicsChart />
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Карта тональности (30 дней)</CardTitle>
          </CardHeader>
          <CardContent>
            <SentimentDonut />
          </CardContent>
        </Card>
        
        <Card className="md:col-span-2 lg:col-span-3">
          <CardHeader>
            <CardTitle>Топ-10 Ключевых тем (30 дней)</CardTitle>
          </CardHeader>
          <CardContent>
            <TopicsBarChart />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}