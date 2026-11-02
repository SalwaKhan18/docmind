import { cloneElement, isValidElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";

import type { Source } from "../types";

interface Props {
  content: string;
  sources: Source[];
  onCitation: (source: Source) => void;
}

function renderCitations(
  node: ReactNode,
  sources: Source[],
  onCitation: (source: Source) => void,
  keyPrefix = "citation",
): ReactNode {
  if (typeof node === "string") {
    return node.split(/(\[\d+\])/g).map((part, index) => {
      const match = /^\[(\d+)\]$/.exec(part);
      const source = match ? sources[Number(match[1]) - 1] : undefined;
      if (!match || !source) return part;
      return (
        <button
          className="citation-chip"
          key={`${keyPrefix}-${index}`}
          onClick={() => onCitation(source)}
          type="button"
          aria-label={`Open source ${match[1]}: ${source.filename}, page ${source.page}`}
        >
          [{match[1]}]
        </button>
      );
    });
  }
  if (Array.isArray(node)) {
    return node.map((child, index) =>
      renderCitations(child, sources, onCitation, `${keyPrefix}-${index}`),
    );
  }
  if (isValidElement<{ children?: ReactNode }>(node)) {
    return cloneElement(node, undefined, renderCitations(node.props.children, sources, onCitation));
  }
  return node;
}

export function CitedMarkdown({ content, sources, onCitation }: Props) {
  const components: Components = {
    p: ({ children }) => (
      <p>{renderCitations(children, sources, onCitation)}</p>
    ),
    li: ({ children }) => (
      <li>{renderCitations(children, sources, onCitation)}</li>
    ),
  };
  return <ReactMarkdown components={components}>{content}</ReactMarkdown>;
}
