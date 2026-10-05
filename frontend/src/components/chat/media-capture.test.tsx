import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ImageExtractionData } from "@/lib/api/client";
import { MediaCapture } from "./media-capture";

const apiMocks = vi.hoisted(() => ({
  extractImage: vi.fn(),
  transcribeAudio: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  ...apiMocks,
}));

describe("MediaCapture", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:preview"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("previews an image, reports upload progress, and returns extracted text", async () => {
    let finishUpload: ((value: ImageExtractionData) => void) | undefined;
    apiMocks.extractImage.mockImplementation(
      (_file: File, onProgress?: (percentage: number) => void) => {
        onProgress?.(42);
        return new Promise<ImageExtractionData>((resolve) => {
          finishUpload = resolve;
        });
      },
    );
    const onTextReady = vi.fn();
    const user = userEvent.setup();
    render(<MediaCapture disabled={false} onTextReady={onTextReady} />);

    const file = new File(["image data"], "receipt.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("Image"), file);

    expect(await screen.findByAltText("Preview of receipt.png")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Media upload progress" })).toHaveValue(42);

    await act(async () => {
      finishUpload?.({
        media_type: "image",
        text: "Receipt: INR 450 for groceries.",
        content_type: "image/png",
        width: 640,
        height: 480,
      });
    });

    await waitFor(() =>
      expect(onTextReady).toHaveBeenCalledWith("Receipt: INR 450 for groceries.", "image"),
    );
  });
});
