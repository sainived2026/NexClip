import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';        // GitHub Flavored Markdown: tables, strikethrough
import remarkBreaks from 'remark-breaks';  // Line breaks
import rehypeHighlight from 'rehype-highlight';  // Code syntax highlighting
import rehypeSanitize from 'rehype-sanitize';    // XSS protection
import { Copy } from 'lucide-react';
import 'highlight.js/styles/github-dark.css'; // Or another highlight style

// Optional copy button component for code blocks
const CopyButton = ({ content }: { content: string }) => {
    const [copied, setCopied] = React.useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <button
            onClick={handleCopy}
            className="absolute top-2 right-2 p-1.5 rounded-md bg-white/10 hover:bg-white/20 text-gray-300 transition-colors z-10"
            title="Copy code"
        >
            {copied ? <span className="text-xs text-green-400 font-medium px-1">Copied</span> : <Copy className="w-4 h-4" />}
        </button>
    );
};

interface MarkdownRendererProps {
    content: string;
    isStreaming?: boolean;
}

export function MarkdownRenderer({ content, isStreaming = false }: MarkdownRendererProps) {
    return (
        <div className={`markdown-body ${isStreaming ? 'streaming' : ''}`}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                rehypePlugins={[rehypeHighlight, rehypeSanitize]}
                components={{
                    // Custom renderers for every markdown element
                    h1: ({ children }) => (
                        <h1 className="nex-h1">{children}</h1>
                    ),
                    h2: ({ children }) => (
                        <h2 className="nex-h2">{children}</h2>
                    ),
                    h3: ({ children }) => (
                        <h3 className="nex-h3">{children}</h3>
                    ),
                    p: ({ children }) => (
                        <p className="nex-p">{children}</p>
                    ),
                    table: ({ children }) => (
                        <div className="nex-table-wrapper">
                            <table className="nex-table">{children}</table>
                        </div>
                    ),
                    th: ({ children }) => (
                        <th className="nex-th">{children}</th>
                    ),
                    td: ({ children }) => (
                        <td className="nex-td">{children}</td>
                    ),
                    code: ({ className, children, ...props }: any) => {
                        const match = /language-(\w+)/.exec(className || '');
                        const isInline = !match && (typeof children === 'string' && !children.includes('\n'));

                        if (isInline) {
                            return (
                                <code className="nex-inline-code">{children}</code>
                            );
                        }

                        return (
                            <div className="nex-code-block relative mt-4 mb-4 rounded-lg overflow-hidden bg-[#1E1E1E] border border-white/10">
                                <div className="flex items-center justify-between px-4 py-2 bg-black/40 border-b border-white/5">
                                    <span className="text-xs text-gray-400 font-mono">
                                        {className ? className.replace('language-', '') : 'code'}
                                    </span>
                                    <CopyButton content={String(children)} />
                                </div>
                                <div className="p-4 overflow-x-auto text-[13px] leading-relaxed relative">
                                    <code className={className}>{children}</code>
                                </div>
                            </div>
                        );
                    },
                    blockquote: ({ children }) => (
                        <blockquote className="nex-blockquote">{children}</blockquote>
                    ),
                    ul: ({ children }) => (
                        <ul className="nex-ul">{children}</ul>
                    ),
                    ol: ({ children }) => (
                        <ol className="nex-ol">{children}</ol>
                    ),
                    li: ({ children }) => (
                        <li className="nex-li">{children}</li>
                    ),
                    strong: ({ children }) => (
                        <strong className="nex-strong font-semibold text-white">{children}</strong>
                    ),
                    em: ({ children }) => (
                        <em className="nex-em text-gray-300 italic">{children}</em>
                    ),
                    hr: () => <hr className="nex-hr my-6 border-white/10" />,
                    a: ({ href, children }) => (
                        <a href={href} className="nex-link text-cyan-400 hover:text-cyan-300 underline underline-offset-2 decoration-cyan-400/30 transition-colors" target="_blank" rel="noopener noreferrer">
                            {children}
                        </a>
                    ),
                }}
            >
                {content}
            </ReactMarkdown>

            {/* Blinking cursor shown only during active streaming */}
            {isStreaming && <span className="streaming-cursor" aria-hidden="true" />}
        </div>
    );
}
