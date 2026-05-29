import { fetch } from "expo/fetch";

import { isNetworkDebug, logError, logRequest, logResponse } from "@/lib/debug";

// Response envelope type - all app routes return { data: T }
interface ApiResponse<T> {
  data: T;
}

const baseUrl = process.env.EXPO_PUBLIC_BACKEND_URL!;

const request = async <T>(
  url: string,
  options: { method?: string; body?: string } = {}
): Promise<T> => {
  // expo/fetch bypasses the global fetch patch, so log it here directly.
  const method = options.method ?? "GET";
  const fullUrl = `${baseUrl}${url}`;
  const headers = options.body ? { "Content-Type": "application/json" } : undefined;
  const debug = isNetworkDebug();
  const start = debug ? Date.now() : 0;
  if (debug) logRequest(method, fullUrl, headers, options.body);

  let response: Awaited<ReturnType<typeof fetch>>;
  try {
    response = await fetch(fullUrl, { ...options, headers });
  } catch (e) {
    if (debug) logError(method, fullUrl, e, Date.now() - start);
    throw e;
  }
  if (debug) logResponse(method, fullUrl, response.status, Date.now() - start);

  // 1. Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  // 2. JSON responses: parse and unwrap { data }
  const contentType = response.headers.get("content-type");
  if (contentType?.includes("application/json")) {
    const json: ApiResponse<T> = await response.json();
    return json.data;
  }

  // 3. Non-JSON: return undefined
  return undefined as T;
};

export const api = {
  get: <T>(url: string) => request<T>(url),
  post: <T>(url: string, body: any) =>
    request<T>(url, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(url: string, body: any) =>
    request<T>(url, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(url: string) => request<T>(url, { method: "DELETE" }),
  patch: <T>(url: string, body: any) =>
    request<T>(url, { method: "PATCH", body: JSON.stringify(body) }),
};
