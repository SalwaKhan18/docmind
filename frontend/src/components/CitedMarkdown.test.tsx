import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CitedMarkdown } from "./CitedMarkdown";

describe("CitedMarkdown", () => {
  it("renders a source citation as a clickable chip", () => {
    const onCitation = vi.fn();
    const source = {
      id: "chunk-1",
      filename: "guide.pdf",
      page: 4,
      snippet: "Relevant text",
      vector_score: 0.8,
      bm25_score: 0.5,
      rrf_score: 0.03,
      rerank_score: 0.9,
    };

    render(
      <CitedMarkdown
        content="The answer is supported [1]."
        sources={[source]}
        onCitation={onCitation}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /guide.pdf, page 4/i }));
    expect(onCitation).toHaveBeenCalledWith(source);
  });
});
