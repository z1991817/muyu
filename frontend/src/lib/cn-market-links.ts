const SINA_INDEX_SYMBOLS: Record<string, string> = {
  "000001": "sh000001",
  "000300": "sh000300",
  "000905": "sh000905",
  "000688": "sh000688",
};

type CnMarketLinkedItem = {
  symbol: string;
  url?: string;
};

function normalizeSymbol(symbol: string): string {
  return symbol.trim();
}

export function sinaMarketPrefix(symbol: string): "sh" | "sz" | "bj" {
  const normalized = normalizeSymbol(symbol);
  if (/^(8|4|9)/.test(normalized)) return "bj";
  if (/^(6|5)/.test(normalized)) return "sh";
  return "sz";
}

export function sinaStockUrl(symbol: string): string {
  const normalized = normalizeSymbol(symbol);
  if (!/^\d{6}$/.test(normalized)) return "https://finance.sina.com.cn/";
  return `https://finance.sina.com.cn/realstock/company/${sinaMarketPrefix(normalized)}${normalized}/nc.shtml`;
}

export function sinaIndexUrl(symbol: string): string {
  const normalized = normalizeSymbol(symbol);
  const sinaSymbol = SINA_INDEX_SYMBOLS[normalized];
  if (!sinaSymbol) return "https://finance.sina.com.cn/stock/";
  return `https://finance.sina.com.cn/realstock/company/${sinaSymbol}/nc.shtml`;
}

export function cnStockUrl(item: CnMarketLinkedItem): string {
  return item.url || sinaStockUrl(item.symbol);
}
