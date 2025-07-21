import { InsightCardData } from "@/types/insight";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function InsightCard({ insight }: { insight: InsightCardData }) {
  const { post_text, post_created_at, channel_name, analysis } = insight;

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-start">
            <div>
                <CardTitle>Инсайт по посту из "{channel_name}"</CardTitle>
                <CardDescription>
                    Опубликовано: {new Date(post_created_at).toLocaleString()}
                </CardDescription>
            </div>
            {/* Здесь может быть иконка-индикатор тональности */}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <h4 className="font-semibold mb-2">Резюме от AI:</h4>
          <p className="text-sm text-muted-foreground">{analysis.summary}</p>
        </div>
        {analysis.key_topics && (
          <div>
            <h4 className="font-semibold mb-2">Ключевые темы:</h4>
            <div className="flex flex-wrap gap-2">
              {analysis.key_topics.map((topic, index) => (
                <Badge key={index} variant="secondary">{topic}</Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
      <CardFooter>
        <p className="text-xs text-muted-foreground">
            Проанализировано с помощью: {analysis.model_used || "N/A"}
        </p>
      </CardFooter>
    </Card>
  );
}