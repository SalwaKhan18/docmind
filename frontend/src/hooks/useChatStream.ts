import { useCallback, useRef, useState } from "react";

import { streamChat } from "../api/client";
import type { ChatRequest, Source } from "../types";

interface StreamHandlers {
  onSources: (sources: Source[], debug: Source[]) => void;
  onToken: (token: string) => void;
  onDone: (conversationId: string) => void;
}

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    setIsStreaming(false);
  }, []);

  const send = useCallback(
    async (payload: ChatRequest, handlers: StreamHandlers) => {
      controller.current?.abort();
      const abortController = new AbortController();
      controller.current = abortController;
      setError(null);
      setIsStreaming(true);
      try {
        await streamChat(payload, handlers, abortController.signal);
      } catch (reason) {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(reason instanceof Error ? reason.message : "The request failed");
        }
      } finally {
        if (controller.current === abortController) {
          controller.current = null;
          setIsStreaming(false);
        }
      }
    },
    [],
  );

  return { send, stop, isStreaming, error, clearError: () => setError(null) };
}
