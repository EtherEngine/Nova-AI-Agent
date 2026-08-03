import { memo } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { CodeBlock } from "@/components/CodeBlock";

const components: Components = {
  // Render fenced code blocks with the copyable CodeBlock; keep inline code plain.
  code({ className, children, ...props }) {
    const text = String(children ?? "");
    const match = /language-(\w+)/.exec(className ?? "");
    const isBlock = Boolean(match) || text.includes("\n");

    if (isBlock) {
      return (
        <CodeBlock code={text.replace(/\n$/, "")} language={match?.[1]} />
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  // The CodeBlock already renders its own <pre>; avoid nesting block elements.
  pre({ children }) {
    return <>{children}</>;
  },
  a({ children, ...props }) {
    return (
      <a {...props} target="_blank" rel="noreferrer noopener">
        {children}
      </a>
    );
  },
};

interface MarkdownRendererProps {
  content: string;
}

/** Renders trusted agent Markdown with GFM (tables, lists, links, code). */
function MarkdownRendererBase({ content }: MarkdownRendererProps) {
  return (
    <div className="prose-agent">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </Markdown>
    </div>
  );
}

export const MarkdownRenderer = memo(MarkdownRendererBase);
