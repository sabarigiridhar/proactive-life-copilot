import { afterEach, describe, expect, it, vi } from "vitest";
import { streamMessage } from "./client";

describe("streamMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses split SSE frames and exposes progressive deltas", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: status\ndata: {"stage":"thinking"}\n\nevent: message.delta\ndata: {"delta":"Hel',
          ),
        );
        controller.enqueue(
          encoder.encode(
            'lo "}\n\nevent: message.complete\ndata: {"thread_id":"thread-1","response_type":"message","assistant_text":"Hello ","draft":null,"evidence":[]}\n\n',
          ),
        );
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
        ),
    );
    const onDelta = vi.fn();
    const onStatus = vi.fn();

    const result = await streamMessage({ message: "Hello", source: "text" }, { onDelta, onStatus });

    expect(onStatus).toHaveBeenCalledWith("thinking");
    expect(onDelta).toHaveBeenCalledWith("Hello ");
    expect(result.thread_id).toBe("thread-1");
    expect(result.assistant_text).toBe("Hello ");
  });

  it("surfaces safe SSE errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('event: error\ndata: {"message":"Please try again."}\n\n', { status: 200 }),
        ),
    );

    await expect(streamMessage({ message: "Hello", source: "text" })).rejects.toThrow(
      "Please try again.",
    );
  });
});
