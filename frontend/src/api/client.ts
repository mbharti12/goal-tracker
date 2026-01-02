import type { ApiErrorResponse } from "./types";

type JsonRequestInit = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

const defaultBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";
const normalizedBaseUrl = defaultBaseUrl.replace(/\/$/, "");

const buildUrl = (path: string) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBaseUrl}${normalizedPath}`;
};

export async function apiRequest<T>(path: string, options: JsonRequestInit = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const finalHeaders = new Headers(headers);
  let finalBody: BodyInit | undefined;

  if (body !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    finalBody = JSON.stringify(body);
  }

  try {
    const response = await fetch(buildUrl(path), {
      ...rest,
      headers: finalHeaders,
      body: finalBody,
    });

    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");

    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const detail =
        payload && typeof payload === "object" && "detail" in payload
          ? String((payload as ApiErrorResponse).detail ?? response.statusText)
          : response.statusText;
      throw new ApiError(detail || "Request failed", response.status, payload);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    const message = error instanceof Error ? error.message : "Network error";
    throw new ApiError(message, 0);
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.data && typeof error.data === "object" && "detail" in error.data) {
      return String((error.data as ApiErrorResponse).detail ?? error.message);
    }
    return error.message || `Request failed (${error.status})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}
