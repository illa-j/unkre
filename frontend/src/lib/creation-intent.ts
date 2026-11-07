const studioOrigin = "https://unkre.local";

/** Only return an internal Studio destination, never an OAuth open redirect. */
export function studioDestination(value: unknown): string {
  if (typeof value !== "string" || value.length > 12000 || !value.startsWith("/") || value.startsWith("//") || /[\\\r\n]/.test(value)) return "/studio";
  try {
    const url = new URL(value, studioOrigin);
    if (url.origin !== studioOrigin || !(url.pathname === "/studio" || url.pathname.startsWith("/studio/"))) return "/studio";
    const search = new URLSearchParams();
    for (const key of ["model", "prompt", "seed", "preset"]) {
      const item = url.searchParams.get(key);
      if (item) search.set(key, item.slice(0, key === "prompt" ? 8192 : 150));
    }
    const loras = url.searchParams.getAll("lora")
      .flatMap(item => item.split(","))
      .map(item => item.trim())
      .filter(Boolean)
      .slice(0, 100);
    if (loras.length) search.set("lora", loras.join(",").slice(0, 4000));
    const reference = url.searchParams.get("reference");
    if (reference) search.set("reference", reference.slice(0, 150));
    return `${url.pathname}${search.size ? `?${search}` : ""}`;
  } catch { return "/studio"; }
}

export function creationHref(values: { model?: string; prompt?: string; lora?: string | string[]; seed?: string; preset?: string; reference?: boolean } = {}) {
  const search = new URLSearchParams();
  for (const key of ["model", "prompt", "seed", "preset"] as const) if (values[key]) search.set(key, values[key]);
  const lora = Array.isArray(values.lora) ? values.lora.filter(Boolean).join(",") : values.lora;
  if (lora) search.set("lora", lora);
  if (values.reference) search.set("reference", "1");
  return `/studio${search.size ? `?${search}` : ""}`;
}

/** `label` lets callers match the friendly catalog title instead of the technical name. */
export function resolveCreationModel<T extends { id: string; name: string }>(items: T[], selection: string, label: (item: T) => string = item => item.name): T | undefined {
  const name = selection.trim().toLowerCase();
  if (!name) return items[0];
  return items.find(item => item.id === selection)
    ?? items.find(item => item.name.trim().toLowerCase() === name)
    ?? items.find(item => label(item).toLowerCase() === name)
    ?? items.find(item => item.name.toLowerCase().includes(name))
    ?? items.find(item => label(item).toLowerCase().includes(name));
}

/** Reference photos are supported only by this model, not other Qwen variants. */
export function supportsReferenceImages(model: { name: string } | undefined): boolean {
  return model?.name.trim().toLowerCase() === "qwen image 2.1";
}
