export interface SubCategoryBreakdown {
  [subCategory: string]: number;
}

export interface VerticalSummary {
  total: number;
  sub_categories: SubCategoryBreakdown;
}

export interface CycleSummaryResponse {
  cycle_id: string;
  summary: string;
  verticals: Record<string, VerticalSummary>;
  total_startups: number;
}

export interface CycleSummaryError {
  error: string;
}
