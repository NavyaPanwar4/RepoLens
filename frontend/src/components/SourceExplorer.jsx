import { useEffect, useMemo, useState } from "react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism"
import client from "../api/client"
import styles from "./SourceExplorer.module.css"

function languageFor(path) {
  const extension = path.split(".").pop()?.toLowerCase()
  return ({ py: "python", js: "javascript", jsx: "jsx", ts: "typescript", tsx: "tsx" })[extension] || extension || "text"
}

export default function SourceExplorer({ repoId, files = [], selectedFile, selectedLine, onSelectFile, onAskAboutFile }) {
  const [search, setSearch] = useState("")
  const [source, setSource] = useState("")
  const [loadedFile, setLoadedFile] = useState("")
  const [errorFile, setErrorFile] = useState("")
  const visibleFiles = useMemo(() => files.map(file => file.id).filter(path => path.toLowerCase().includes(search.toLowerCase())), [files, search])

  useEffect(() => {
    if (!selectedFile) return
    let active = true
    client.get(`/repositories/${repoId}/source`, { params: { path: selectedFile } })
      .then(({ data }) => {
        if (active) {
          setSource(data.content)
          setLoadedFile(selectedFile)
          setErrorFile("")
        }
      })
      .catch(() => { if (active) setErrorFile(selectedFile) })
    return () => { active = false }
  }, [repoId, selectedFile])

  if (!files.length) return <div className={styles.empty}>No source files are available for this analysis.</div>

  const loading = Boolean(selectedFile) && loadedFile !== selectedFile && errorFile !== selectedFile
  const error = errorFile === selectedFile

  return (
    <div className={styles.explorer}>
      <aside className={styles.sidebar} aria-label="Repository files">
        <div className={styles.sidebarHeader}><span>Source files</span><span>{files.length}</span></div>
        <input className={styles.search} value={search} onChange={event => setSearch(event.target.value)} placeholder="Filter files…" aria-label="Filter source files" />
        <div className={styles.fileList}>
          {visibleFiles.map(path => <button key={path} className={path === selectedFile ? styles.fileActive : styles.file} onClick={() => onSelectFile(path, 1)} title={path}>{path}</button>)}
        </div>
      </aside>
      <section className={styles.viewer}>
        <header className={styles.viewerHeader}>
          <span className={styles.path}>{selectedFile || "Select a file"}</span>
          {selectedFile && <button className={styles.askButton} onClick={() => onAskAboutFile(selectedFile)}>Ask AI about file</button>}
        </header>
        {loading && <div className={styles.state}>Loading source…</div>}
        {error && <div className={styles.error}>The stored source file could not be loaded.</div>}
        {!loading && !error && selectedFile && (
          <SyntaxHighlighter language={languageFor(selectedFile)} style={vscDarkPlus} showLineNumbers wrapLongLines lineProps={lineNumber => ({ className: lineNumber === selectedLine ? styles.highlightedLine : "" })} customStyle={{ margin: 0, minHeight: "100%", borderRadius: 0, background: "#111" }}>
            {source}
          </SyntaxHighlighter>
        )}
      </section>
    </div>
  )
}
