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

export interface CnMarketIndex {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  url: string;
  updatedAt: string;
  disclaimer: string;
}

export interface CnMarketStock {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  volume: string;
  turnover: string;
  url: string;
  updatedAt: string;
  disclaimer: string;
}

export interface CnFundFlow {
  name: string;
  value: string;
  changePct: number;
  direction: string;
}

export interface CnLimitStock {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  reason: string;
  url: string;
}

export interface CnMarketAnalysis {
  fundFlows: CnFundFlow[];
  limitUp: CnLimitStock[];
  limitDown: CnLimitStock[];
}

export interface CnMarketResponse {
  indices: CnMarketIndex[];
  stocks: CnMarketStock[];
  analysis: CnMarketAnalysis;
  stale: boolean;
  updatedAt: string;
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
