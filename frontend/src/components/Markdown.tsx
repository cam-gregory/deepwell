import type { ReactNode } from "react";

/** Renders inline markdown (bold + [Source N] citations) as React nodes, escaping everything else as plain text. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Split on **bold** and [Source N] tokens, keeping the delimiters.
  const tokenRe = /(\*\*.+?\*\*|\[Source\s*\d+\])/gi;
  const parts = text.split(tokenRe);

  parts.forEach((part, i) => {
    if (!part) return;
    const key = `${keyPrefix}-${i}`;
    const boldMatch = part.match(/^\*\*(.+)\*\*$/);
    const citeMatch = part.match(/^\[Source\s*(\d+)\]$/i);
    if (boldMatch) {
      nodes.push(<strong key={key}>{boldMatch[1]}</strong>);
    } else if (citeMatch) {
      nodes.push(
        <span
          key={key}
          className="mx-0.5 inline-flex items-center rounded-md bg-accent-soft px-1.5 py-0.5 text-xs font-semibold text-accent-ink nums align-baseline"
        >
          {citeMatch[1]}
        </span>,
      );
    } else {
      nodes.push(part);
    }
  });

  return nodes;
}

/** Minimal offline markdown renderer: headings, blockquote callouts, lists, and paragraphs. */
export default function Markdown({ text }: { text: string }) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let listItems: ReactNode[] = [];
  let listType: "ul" | "ol" | null = null;

  function closeList() {
    if (listType) {
      const Tag = listType;
      blocks.push(<Tag key={`list-${blocks.length}`}>{listItems}</Tag>);
      listItems = [];
      listType = null;
    }
  }

  lines.forEach((raw, idx) => {
    const line = raw.trim();
    const key = `line-${idx}`;
    if (line === "") {
      closeList();
      return;
    }

    let m = line.match(/^#{2,6}\s+(.*)$/);
    if (m) {
      closeList();
      const level = line.startsWith("###") ? "h3" : "h2";
      const Tag = level as "h2" | "h3";
      const cls =
        level === "h2"
          ? "font-display text-lg font-semibold tracking-[-0.01em] mt-6 mb-2 pb-1.5 border-b border-line text-ink"
          : "text-[15px] font-semibold mt-4 mb-1.5 text-ink-soft";
      blocks.push(
        <Tag key={key} className={cls}>
          {renderInline(m[1], key)}
        </Tag>,
      );
      return;
    }

    m = line.match(/^#\s+(.*)$/);
    if (m) {
      closeList();
      blocks.push(
        <h2 key={key} className="font-display text-lg font-semibold tracking-[-0.01em] mt-6 mb-2 pb-1.5 border-b border-line text-ink">
          {renderInline(m[1], key)}
        </h2>,
      );
      return;
    }

    m = line.match(/^>\s?(.*)$/);
    if (m) {
      closeList();
      const warn = /⚠|warning|caution|danger/i.test(m[1]);
      blocks.push(
        <blockquote
          key={key}
          className={
            warn
              ? "my-4 py-3 px-4 rounded-lg bg-data-clay/10 border-l-4 border-data-clay text-data-clay"
              : "my-4 py-3 px-4 rounded-lg bg-surface-sunk border-l-4 border-line-strong text-ink-soft"
          }
        >
          {renderInline(m[1], key)}
        </blockquote>,
      );
      return;
    }

    m = line.match(/^\d+[.)]\s+(.*)$/);
    if (m) {
      if (listType !== "ol") {
        closeList();
        listType = "ol";
      }
      listItems.push(
        <li key={key} className="my-1.5">
          {renderInline(m[1], key)}
        </li>,
      );
      return;
    }

    m = line.match(/^[-*+]\s+(.*)$/);
    if (m) {
      if (listType !== "ul") {
        closeList();
        listType = "ul";
      }
      listItems.push(
        <li key={key} className="my-1.5">
          {renderInline(m[1], key)}
        </li>,
      );
      return;
    }

    closeList();
    blocks.push(
      <p key={key} className="my-3">
        {renderInline(line, key)}
      </p>,
    );
  });
  closeList();

  return <div className="leading-relaxed [&>ul]:my-3 [&>ul]:pl-6 [&>ol]:my-3 [&>ol]:pl-6">{blocks}</div>;
}
