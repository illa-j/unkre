export type StudioIconName = "create" | "gallery" | "lora" | "credits" | "gift" | "settings" | "arrow" | "plus" | "heart" | "download" | "close" | "search" | "upload" | "check" | "copy" | "menu" | "image" | "trash" | "preset" | "bookmark";

const paths: Record<StudioIconName, string> = {
  create: "M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4",
  gallery: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  lora: "m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5",
  credits: "M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM12 8v8M9 10h5M10 14h5",
  gift: "M4 9h16v4H4zM5 13v8h14v-8M12 9v12M12 9C9 9 7 7.6 7 5.8 7 4.2 8.2 3 9.7 3 11.2 3 12 4.6 12 6.2v2.8Zm0 0c3 0 5-1.4 5-3.2C17 4.2 15.8 3 14.3 3 12.8 3 12 4.6 12 6.2V9Z",
  settings: "M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6",
  arrow: "M5 12h14m-6-6 6 6-6 6", plus: "M12 5v14M5 12h14",
  heart: "M20.8 5.6a5.5 5.5 0 0 0-7.8 0L12 6.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 22l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5", close: "m6 6 12 12M18 6 6 18",
  search: "M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Zm5.5-2 5 5",
  upload: "M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5", check: "m5 12 4 4L19 6",
  copy: "M8 8h13v13H8zM16 8V3H3v13h5", menu: "M4 6h16M4 12h16M4 18h16",
  image: "M3 3h18v18H3zM3 17l6-6 4 4 3-3 5 5M16 7h.01", trash: "M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7",
  preset: "M6 3h12v18l-6-4-6 4zM9 8h6M9 12h4",
  bookmark: "M6 3h12v18l-6-4-6 4z",
};

export function StudioIcon({ name, size = 20 }: { name: StudioIconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
