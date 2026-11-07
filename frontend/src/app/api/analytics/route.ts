import { site } from "@/lib/site";
import { validAnalyticsPayload } from "@/lib/analytics";

export async function POST(request: Request) {
  if (request.headers.get("sec-fetch-site") === "cross-site") return new Response(null, { status: 403 });
  const origin = request.headers.get("origin");
  if (origin) {
    let sameHost = false;
    try {
      const url = new URL(origin);
      sameHost = ["http:", "https:"].includes(url.protocol) && url.host === request.headers.get("host");
    } catch { return new Response(null, { status: 403 }); }
    if (!sameHost && origin !== new URL(request.url).origin && origin !== site.url?.origin) return new Response(null, { status: 403 });
  }
  if (!request.headers.get("content-type")?.startsWith("application/json")) return new Response(null, { status: 415 });
  if (Number(request.headers.get("content-length")) > 1024) return new Response(null, { status: 413 });
  const body = await request.text();
  if (body.length > 1024) return new Response(null, { status: 413 });
  let payload;
  try { payload = validAnalyticsPayload(JSON.parse(body)); } catch { return new Response(null, { status: 400 }); }
  if (!payload) return new Response(null, { status: 400 });
  console.info(JSON.stringify({ type: "unkre.analytics", timestamp: new Date().toISOString(), ...payload }));
  return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}
