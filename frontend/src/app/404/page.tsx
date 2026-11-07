import { notFound } from "next/navigation";

// Nginx rewrites blocked admin routes here. Keeping the rendering in Next means
// /admin looks exactly like every other unknown page, including its 404 status.
export default function NotFoundProxy(): never {
  notFound();
}
