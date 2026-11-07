"use client";

import { createContext, useContext, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { Workflow } from "@/lib/api-types";
import { useApiData } from "@/lib/use-api-data";
import { useSession } from "../session-provider";

type Catalog = { workflows: Workflow[]; loading: boolean; error?: string; reload: () => void };
const CatalogContext = createContext<Catalog | null>(null);

export function CatalogProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const data = useApiData(user?.id ?? null, api.workflows);
  return <CatalogContext value={{ workflows: data.data ?? [], loading: data.loading, error: data.error, reload: data.reload }}>{children}</CatalogContext>;
}

export function useCatalog() {
  const value = useContext(CatalogContext);
  if (!value) throw new Error("CatalogProvider is missing");
  return value;
}
