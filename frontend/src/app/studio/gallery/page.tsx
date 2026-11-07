import type { Metadata } from "next";
import { Gallery } from "@/components/studio/gallery";
export const metadata: Metadata = { title: "My images" };
export default function GalleryPage() { return <Gallery />; }
