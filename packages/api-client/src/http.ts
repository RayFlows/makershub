import { ApiRequestError, type ApiErrorPayload } from "./errors";

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: ApiErrorPayload;
  message?: string;
  request_id?: string;
}

export interface ApiRequestOptions {
  method?: HttpMethod;
  body?: unknown;
  token?: string;
}

export interface ApiTransportRequest {
  url: string;
  method: HttpMethod;
  headers: Record<string, string>;
  body?: string;
}

export interface ApiTransportResponse {
  ok: boolean;
  status: number;
  payload: unknown;
}

export type ApiTransport = (request: ApiTransportRequest) => Promise<ApiTransportResponse>;

export function createFetchTransport(fetchImpl: typeof fetch = getGlobalFetch()): ApiTransport {
  return async (request) => {
    const response = await fetchImpl(request.url, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });

    return {
      ok: response.ok,
      status: response.status,
      payload: await parseJsonSafely(response),
    };
  };
}

export interface ApiRequesterOptions {
  baseUrl: string;
  transport?: ApiTransport;
}

export function createApiRequester({ baseUrl, transport = createFetchTransport() }: ApiRequesterOptions) {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");

  return async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (options.token) {
      headers.Authorization = `Bearer ${options.token}`;
    }

    const response = await transport({
      url: `${normalizedBaseUrl}${path}`,
      method: options.method || "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const payload = response.payload as Partial<ApiEnvelope<T>> | null;

    if (!response.ok || payload?.success === false) {
      const error = payload?.error;
      throw new ApiRequestError(
        error?.message || "请求失败",
        error?.code || "HTTP_ERROR",
        response.status,
        { details: error?.details, requestId: payload?.request_id },
      );
    }
    if (payload?.data === undefined) {
      throw new ApiRequestError("响应缺少数据", "EMPTY_RESPONSE", response.status, {
        requestId: payload?.request_id,
      });
    }
    return payload.data;
  };
}

async function parseJsonSafely(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function getGlobalFetch(): typeof fetch {
  if (typeof globalThis.fetch !== "function") {
    throw new Error("No fetch implementation is available");
  }
  return globalThis.fetch.bind(globalThis);
}
