import { describe, expect, it } from "vitest";
import { resolveApiOrigin } from "./config";

describe("resolveApiOrigin", () => {
  it("uses the local FastAPI origin during development", () => {
    expect(resolveApiOrigin(undefined, "development")).toBe("http://127.0.0.1:8000");
  });

  it("normalizes a configured HTTP origin", () => {
    expect(resolveApiOrigin(" https://api.example.com/ ", "production")).toBe(
      "https://api.example.com",
    );
  });

  it("requires explicit production configuration", () => {
    expect(() => resolveApiOrigin(undefined, "production")).toThrow(
      "NEXT_PUBLIC_LIFE_COPILOT_API_URL is required",
    );
  });

  it("rejects non-HTTP URLs", () => {
    expect(() => resolveApiOrigin("file:///private.db", "development")).toThrow(
      "must use HTTP or HTTPS",
    );
  });
});
