import { cnStockUrl, sinaMarketPrefix, sinaStockUrl } from "../src/lib/cn-market-links.js";

function assertEqual(actual: string, expected: string): void {
  if (actual !== expected) {
    throw new Error(`Expected ${expected}, got ${actual}`);
  }
}

assertEqual(sinaMarketPrefix("920575"), "bj");
assertEqual(sinaStockUrl("920575"), "https://finance.sina.com.cn/realstock/company/bj920575/nc.shtml");
assertEqual(sinaStockUrl("600519"), "https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml");
assertEqual(sinaStockUrl("300750"), "https://finance.sina.com.cn/realstock/company/sz300750/nc.shtml");
assertEqual(
  cnStockUrl({ symbol: "920575", url: "https://quote.eastmoney.com/bj/920575.html" }),
  "https://quote.eastmoney.com/bj/920575.html",
);
