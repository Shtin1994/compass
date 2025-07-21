export interface DynamicsDataPoint {
  date: string;
  posts: number;
  comments: number;
}

export interface SentimentDataPoint {
  positive_avg: number;
  negative_avg: number;
  neutral_avg: number;
}

export interface TopicDataPoint {
  topic: string;
  count: number;
}