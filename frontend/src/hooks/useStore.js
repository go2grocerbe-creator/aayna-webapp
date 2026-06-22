import { useQuery } from "@tanstack/react-query";
import { getSettings, getCategories } from "@/lib/api";

export const useSettings = () =>
  useQuery({ queryKey: ["settings"], queryFn: getSettings, staleTime: 5 * 60_000 });

export const useCategories = () =>
  useQuery({ queryKey: ["categories"], queryFn: getCategories, staleTime: 5 * 60_000 });
