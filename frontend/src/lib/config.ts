const LOCAL_API_ORIGIN = "http://127.0.0.1:8000";

export function resolveApiOrigin(
  configuredValue: string | undefined,
  environment: string | undefined,
): string {
  const candidate = configuredValue?.trim();
  if (!candidate && environment === "production") {
    throw new Error("NEXT_PUBLIC_LIFE_COPILOT_API_URL is required in production.");
  }

  const value = candidate || LOCAL_API_ORIGIN;
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error("NEXT_PUBLIC_LIFE_COPILOT_API_URL must be an absolute URL.");
  }
  if (!new Set(["http:", "https:"]).has(parsed.protocol)) {
    throw new Error("NEXT_PUBLIC_LIFE_COPILOT_API_URL must use HTTP or HTTPS.");
  }
  return parsed.toString().replace(/\/$/, "");
}

export function getApiOrigin(): string {
  return resolveApiOrigin(process.env.NEXT_PUBLIC_LIFE_COPILOT_API_URL, process.env.NODE_ENV);
}
