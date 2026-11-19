import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism"
import styles from "./MarkdownText.module.css"

export default function MarkdownText({ children }) {
  if (!children) return null

  return (
    <div className={styles.markdown}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, title, children }) => (
            <a href={href} title={title} target="_blank" rel="noreferrer">{children}</a>
          ),
          code: ({ className, children: code, ...props }) => {
            const match = /language-(\w+)/.exec(className || "")
            if (!match) return <code className={styles.inlineCode} {...props}>{code}</code>
            return (
              <SyntaxHighlighter
                language={match[1]}
                style={vscDarkPlus}
                customStyle={{ margin: "12px 0", borderRadius: 8, fontSize: 12 }}
              >
                {String(code).replace(/\n$/, "")}
              </SyntaxHighlighter>
            )
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
