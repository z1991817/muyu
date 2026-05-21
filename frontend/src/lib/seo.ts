export const SITE_NAME = "摸鱼热榜";
export const SITE_DESCRIPTION =
  "摸鱼热榜聚合微博、知乎、B站、抖音、GitHub、V2EX 等公开热榜链接，提供干净的热搜导航与美股大盘信息展示。";

export const SITE_URL = (import.meta.env.PUBLIC_SITE_URL ?? "https://moyu.example.com")
  .replace(/\/+$/, "");

export const DEFAULT_OG_IMAGE = `${SITE_URL}/logo-orange-4-punch.svg`;

export function absoluteUrl(path = "/"): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function jsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
