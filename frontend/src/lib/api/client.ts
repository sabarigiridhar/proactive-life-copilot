import createClient from "openapi-fetch";
import { getApiOrigin } from "@/lib/config";
import type { components, paths } from "./schema";

export type HealthData = components["schemas"]["HealthData"];
export type ConversationSummary = components["schemas"]["ConversationSummaryData"];
export type ConversationDetail = components["schemas"]["ConversationDetailData"];
export type ConversationMessage = components["schemas"]["ConversationMessageData"];
export type MessageRequest = components["schemas"]["MessageRequest"];
export type MessageData = components["schemas"]["MessageData"];
export type DailyLogDraft = components["schemas"]["DailyLogDraft"];
export type ConfirmLogData = components["schemas"]["ConfirmLogData"];
export type CancelLogData = components["schemas"]["CancelLogData"];
export type TranscriptionData = components["schemas"]["TranscriptionData"];
export type ImageExtractionData = components["schemas"]["ImageExtractionData"];
export type DashboardSummary = components["schemas"]["DashboardSummary"];
export type RecordPage = components["schemas"]["RecordPage"];
export type DomainRecord = RecordPage["items"][number];
export type RecordPatch = components["schemas"]["RecordPatch"];
export type RecordMutationData = components["schemas"]["RecordMutationData"];
export type RecordDeletionData = components["schemas"]["RecordDeletionData"];
export type WealthRecord = components["schemas"]["WealthRecord"];
export type HealthRecord = components["schemas"]["HealthRecord"];
export type LearningRecord = components["schemas"]["LearningRecord"];
export type LearningSearchResult = components["schemas"]["LearningSearchResult"];
export type WeeklyReviewsData = components["schemas"]["WeeklyReviewsData"];
export type SettingsData = components["schemas"]["SettingsData"];
export type SettingsPatch = components["schemas"]["AppPreferencesPatch"];
export type BackupData = components["schemas"]["BackupData"];
export type RecordDomain = "wealth" | "health" | "learning";

export type ApiResult<T> = { ok: true; data: T } | { ok: false; message: string; status?: number };

function requestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}`;
}

function unexpectedMessage(error?: { message: string } | null): string {
  return error?.message ?? "The Life Copilot API returned an unexpected response.";
}

export function createApiClient() {
  const client = createClient<paths>({ baseUrl: getApiOrigin() });
  client.use({
    onRequest({ request }) {
      request.headers.set("x-request-id", requestId());
      return request;
    },
  });
  return client;
}

export async function getHealth(): Promise<ApiResult<HealthData>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/health", {
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return {
        ok: false,
        message: data?.error?.message ?? "The Life Copilot API returned an unexpected response.",
        status: response.status,
      };
    }
    return { ok: true, data: data.data };
  } catch {
    return {
      ok: false,
      message: "The Life Copilot API is unavailable. Start FastAPI and try again.",
    };
  }
}

export async function getConversations(): Promise<ApiResult<ConversationSummary[]>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/conversations", {
      params: { query: { limit: 100 } },
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data.items ?? [] };
  } catch {
    return { ok: false, message: "Conversation history is unavailable." };
  }
}

export async function getConversation(threadId: string): Promise<ApiResult<ConversationDetail>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/conversations/{thread_id}", {
      params: { path: { thread_id: threadId }, query: { message_limit: 500 } },
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "This conversation could not be loaded." };
  }
}

export async function confirmDraft(
  threadId: string,
  draft: DailyLogDraft,
): Promise<ApiResult<ConfirmLogData>> {
  try {
    const { data, response } = await createApiClient().POST("/api/v1/logs/confirm", {
      body: { thread_id: threadId, draft },
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "The extracted records could not be saved." };
  }
}

export async function cancelDraft(threadId: string): Promise<ApiResult<CancelLogData>> {
  try {
    const { data, response } = await createApiClient().POST("/api/v1/logs/cancel", {
      body: { thread_id: threadId },
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "The draft could not be cancelled." };
  }
}

export type StreamCallbacks = {
  onDelta?: (delta: string) => void;
  onStatus?: (stage: string) => void;
  signal?: AbortSignal;
};

type SsePayload = Record<string, unknown>;

function readSseEvent(block: string): { event: string; data: SsePayload } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) as SsePayload };
}

export async function streamMessage(
  payload: MessageRequest,
  callbacks: StreamCallbacks = {},
): Promise<MessageData> {
  const response = await fetch(`${getApiOrigin()}/api/v1/messages/stream`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-request-id": requestId() },
    body: JSON.stringify(payload),
    signal: callbacks.signal,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message ?? `Message request failed (${response.status}).`);
  }
  if (!response.body) throw new Error("The streaming response was empty.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: MessageData | null = null;

  const handleBlock = (block: string) => {
    const parsed = readSseEvent(block);
    if (!parsed) return;
    if (parsed.event === "status") callbacks.onStatus?.(String(parsed.data.stage ?? "thinking"));
    if (parsed.event === "message.delta") callbacks.onDelta?.(String(parsed.data.delta ?? ""));
    if (parsed.event === "message.complete") completed = parsed.data as MessageData;
    if (parsed.event === "error") {
      throw new Error(String(parsed.data.message ?? "The message could not be completed."));
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) handleBlock(block);
    if (done) break;
  }
  if (buffer.trim()) handleBlock(buffer);
  if (!completed) throw new Error("The stream ended before the response completed.");
  return completed;
}

type UploadEnvelope<T> = {
  success: boolean;
  data?: T | null;
  error?: { message: string } | null;
};

function uploadMedia<T>(
  path: "/api/v1/media/transcriptions" | "/api/v1/media/extractions",
  file: File,
  onProgress?: (percentage: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${getApiOrigin()}${path}`);
    request.setRequestHeader("x-request-id", requestId());
    request.responseType = "json";
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    });
    request.addEventListener("load", () => {
      const body = request.response as UploadEnvelope<T> | null;
      if (request.status >= 200 && request.status < 300 && body?.success && body.data) {
        resolve(body.data);
        return;
      }
      reject(new Error(body?.error?.message ?? `Upload failed (${request.status}).`));
    });
    request.addEventListener("error", () => reject(new Error("The media upload was interrupted.")));
    request.addEventListener("abort", () => reject(new Error("The media upload was cancelled.")));
    const form = new FormData();
    form.append("file", file);
    request.send(form);
  });
}

export function transcribeAudio(
  file: File,
  onProgress?: (percentage: number) => void,
): Promise<TranscriptionData> {
  return uploadMedia("/api/v1/media/transcriptions", file, onProgress);
}

export function extractImage(
  file: File,
  onProgress?: (percentage: number) => void,
): Promise<ImageExtractionData> {
  return uploadMedia("/api/v1/media/extractions", file, onProgress);
}

export type DashboardQuery = {
  start_date?: string;
  end_date?: string;
  status_date?: string;
};

export async function getDashboardSummary(
  query: DashboardQuery = {},
): Promise<ApiResult<DashboardSummary>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/dashboard/summary", {
      params: { query },
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "Dashboard data is unavailable." };
  }
}

export type RecordQuery = {
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  search?: string;
  source?: string;
  transaction_type?: "Income" | "Expense";
  currency?: string;
  category?: string;
  merchant?: string;
  workout_type?: string;
  topic?: string;
};

export async function listRecords(
  domain: RecordDomain,
  query: RecordQuery = {},
): Promise<ApiResult<RecordPage>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/logs/{domain}", {
      params: { path: { domain }, query: { page: 1, page_size: 50, ...query } },
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: `${domain} records are unavailable.` };
  }
}

export async function listAllRecords(
  domain: RecordDomain,
  query: Omit<RecordQuery, "page" | "page_size"> = {},
): Promise<ApiResult<DomainRecord[]>> {
  const records: DomainRecord[] = [];
  let page = 1;
  while (true) {
    const result = await listRecords(domain, { ...query, page, page_size: 200 });
    if (!result.ok) return result;
    records.push(...result.data.items);
    if (page >= result.data.total_pages) return { ok: true, data: records };
    page += 1;
  }
}

export async function updateRecord(
  domain: RecordDomain,
  recordId: number,
  patch: RecordPatch,
): Promise<ApiResult<RecordMutationData>> {
  try {
    const { data, response } = await createApiClient().PATCH("/api/v1/logs/{domain}/{record_id}", {
      params: { path: { domain, record_id: recordId } },
      body: patch,
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "The record could not be updated." };
  }
}

export async function deleteRecord(
  domain: RecordDomain,
  recordId: number,
): Promise<ApiResult<RecordDeletionData>> {
  try {
    const { data, response } = await createApiClient().DELETE("/api/v1/logs/{domain}/{record_id}", {
      params: { path: { domain, record_id: recordId }, query: { confirm: true } },
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "The record could not be deleted." };
  }
}

export async function searchLearning(
  query: string,
  filters: { topic?: string; start_date?: string; end_date?: string; limit?: number } = {},
): Promise<ApiResult<LearningSearchResult>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/learning/search", {
      params: { query: { query, limit: 10, ...filters } },
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "Learning notes could not be searched." };
  }
}

export async function getWeeklyReviews(): Promise<ApiResult<WeeklyReviewsData>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/insights/weekly", {
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "Weekly reviews are unavailable." };
  }
}

export async function getSettings(): Promise<ApiResult<SettingsData>> {
  try {
    const { data, response } = await createApiClient().GET("/api/v1/settings", {
      cache: "no-store",
    });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "Settings are unavailable." };
  }
}

export async function updateSettings(patch: SettingsPatch): Promise<ApiResult<SettingsData>> {
  try {
    const { data, response } = await createApiClient().PATCH("/api/v1/settings", { body: patch });
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "Settings could not be saved." };
  }
}

export async function createBackup(): Promise<ApiResult<BackupData>> {
  try {
    const { data, response } = await createApiClient().POST("/api/v1/data/backups");
    if (!response.ok || !data?.success || !data.data) {
      return { ok: false, message: unexpectedMessage(data?.error), status: response.status };
    }
    return { ok: true, data: data.data };
  } catch {
    return { ok: false, message: "The local snapshot could not be created." };
  }
}
