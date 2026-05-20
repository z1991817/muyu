export interface Trend {
  platform: string;
  platformName: string;
  title: string;
  url: string;
  rank: number;
  heat: string;
  source: string;
  updatedAt: string;
}

export interface SourceInfo {
  platform: string;
  platformName: string;
  status: string;
  updatedAt: string;
}

export interface MarketIndex {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  url: string;
  marketStatus: string;
  tradeDate: string;
  updatedAt: string;
  disclaimer: string;
}

export interface MarketStock {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  url: string;
  marketStatus: string;
  tradeDate: string;
  updatedAt: string;
  disclaimer: string;
}

export type RestDayKind = "holiday" | "weekend" | "workday";

export interface CalendarInfo {
  date: string;
  isRestDay: boolean;
  kind: RestDayKind;
  name?: string | null;
}

export interface StocksResponse {
  items: MarketStock[];
  stale: boolean;
  updatedAt: string;
}

export interface HomeResponse {
  trends: Trend[];
  markets: MarketIndex[];
  sources: SourceInfo[];
  calendar: CalendarInfo;
  stale: boolean;
  updatedAt: string;
}

export interface TrendsResponse {
  items: Trend[];
  stale: boolean;
  updatedAt: string;
}

export interface MarketResponse {
  items: MarketIndex[];
  stale: boolean;
  updatedAt: string;
}

export interface SourcesResponse {
  items: SourceInfo[];
  stale: boolean;
  updatedAt: string;
}
