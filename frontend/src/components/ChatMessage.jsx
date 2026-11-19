import { useState } from "react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism"
import MarkdownText from "./MarkdownText"
import styles from "./ChatMessage.module.css"

export default function ChatMessage({ message, onOpenSource }) {
  const [showChunks, setShowChunks] = useState(false)
  const isUser = message.role === "user"

  return (
    <div className={`${styles.wrapper} ${isUser ? styles.user : styles.assistant}`}>
      <div className={styles.label}>{isUser ? "you" : "ai"}</div>
      <div className={`${styles.bubble} ${message.isError ? styles.error : ""}`}>
        {isUser ? (
          <p className={styles.text}>{message.text}</p>
        ) : (
          <MarkdownText>{message.text}</MarkdownText>
        )}

        {message.chunks?.length > 0 && (
          <div className={styles.chunks}>
            <button className={styles.toggle} onClick={() => setShowChunks(v => !v)}>
              {showChunks ? "Hide" : "Show"} {message.chunks.length} source chunks
            </button>
            {showChunks && message.chunks.map((chunk, i) => (
              <div key={i} className={styles.chunk}>
                <div className={styles.chunkMeta}>
                  {chunk.metadata.file.split("/").pop()} · {chunk.metadata.type} · score: {chunk.score}
                </div>
                <button
                  className={styles.openSource}
                  onClick={() => onOpenSource?.(chunk.metadata.file, chunk.metadata.start_line || 1)}
                >
                  Open source
                </button>
                <SyntaxHighlighter
                  language={chunk.metadata.language || "python"}
                  style={vscDarkPlus}
                  customStyle={{ margin: 0, borderRadius: 6, fontSize: 12 }}
                >
                  {chunk.text}
                </SyntaxHighlighter>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
