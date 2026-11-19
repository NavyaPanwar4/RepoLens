import { useMemo, useState } from "react"
import styles from "./GraphView.module.css"

const LANGUAGE_NAMES = {
  py: "Python",
  js: "JavaScript",
  jsx: "React JSX",
  ts: "TypeScript",
  tsx: "React TSX",
  java: "Java",
  rs: "Rust",
  cpp: "C++",
  c: "C",
  md: "Markdown",
  json: "JSON",
  yaml: "YAML",
  yml: "YAML",
  html: "HTML",
  css: "CSS",
  sh: "Shell",
}

function folderFor(path) {
  const parts = path.split("/")
  return parts.length > 1 ? parts.slice(0, -1).join("/") : "Root"
}

function filenameFor(path) {
  return path.split("/").pop() || path
}

function isEntryPoint(node) {
  const name = filenameFor(node.id).toLowerCase()
  return /^(main|app|index|server|cli|entry|manage)\./.test(name)
    || /__(main|init)__\./.test(name)
}

export default function GraphView({ graphData, onNodeClick }) {
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState(null)
  const [view, setView] = useState("overview")

  const nodes = useMemo(() => graphData?.nodes || [], [graphData?.nodes])
  const edges = graphData?.edges || []

  const languageCounts = useMemo(() => {
    const counts = {}
    nodes.forEach(node => {
      counts[node.language || "text"] = (counts[node.language || "text"] || 0) + 1
    })
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [nodes])

  const folders = useMemo(() => {
    const counts = {}
    nodes.forEach(node => {
      const folder = folderFor(node.id)
      counts[folder] = (counts[folder] || 0) + 1
    })
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [nodes])

  const entryPoints = nodes.filter(isEntryPoint)
  const centralFiles = [...nodes]
    .sort((a, b) => (
      (b.in_degree + b.out_degree + b.num_functions + b.num_classes)
      - (a.in_degree + a.out_degree + a.num_functions + a.num_classes)
    ))
    .slice(0, 5)
  const connectedNodes = nodes.filter(node => node.in_degree > 0 || node.out_degree > 0)

  const visibleNodes = nodes.filter(node => {
    const query = search.trim().toLowerCase()
    return !query || node.id.toLowerCase().includes(query)
  })

  function openNode(node) {
    setSelected(node)
  }

  if (!nodes.length) {
    return <div className={styles.empty}>No architecture data is available for this analysis.</div>
  }

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>REPOSITORY OVERVIEW</span>
          <h2>Project structure</h2>
        </div>
        <div className={styles.metrics}>
          <div><strong>{nodes.length}</strong><span>source files</span></div>
          <div><strong>{folders.length}</strong><span>folders</span></div>
          <div><strong>{edges.length}</strong><span>relationships</span></div>
        </div>
      </header>

      <div className={styles.toolbar}>
        <div className={styles.tabs} aria-label="Architecture views">
          {[
            ["overview", "Overview"],
            ["files", "Files"],
            ["connections", "Connections"],
          ].map(([tab, label]) => (
            <button
              key={tab}
              type="button"
              className={view === tab ? styles.tabActive : styles.tab}
              onClick={() => setView(tab)}
            >
              {label}
            </button>
          ))}
        </div>
        {view === "files" && (
          <input
            className={styles.search}
            value={search}
            onChange={event => setSearch(event.target.value)}
            placeholder="Search files"
            aria-label="Search files"
          />
        )}
      </div>

      <div className={styles.content}>
        {view === "overview" && (
          <div className={styles.overview}>
            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <div><span>01</span><h3>Technology stack</h3></div>
                <small>by file type</small>
              </div>
              <div className={styles.languages}>
                {languageCounts.map(([language, count]) => (
                  <div className={styles.language} key={language}>
                    <div className={styles.languageTop}>
                      <strong>{LANGUAGE_NAMES[language] || language.toUpperCase()}</strong>
                      <span>{count} {count === 1 ? "file" : "files"}</span>
                    </div>
                    <div className={styles.bar}>
                      <i style={{ width: `${Math.max((count / nodes.length) * 100, 6)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <div><span>02</span><h3>Project layout</h3></div>
                <small>{folders.length} folders</small>
              </div>
              <div className={styles.folderList}>
                {folders.map(([folder, count]) => (
                  <button
                    type="button"
                    key={folder}
                    className={styles.folderRow}
                    onClick={() => {
                      setSearch(folder === "Root" ? "" : folder)
                      setView("files")
                    }}
                  >
                    <span className={styles.folderIcon}>{folder === "Root" ? "⌂" : "▦"}</span>
                    <span className={styles.folderName}>{folder}</span>
                    <strong>{count}</strong>
                    <span className={styles.arrow}>→</span>
                  </button>
                ))}
              </div>
            </section>

            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <div><span>03</span><h3>Likely entry points</h3></div>
                <small>{entryPoints.length} detected</small>
              </div>
              {entryPoints.length ? (
                <div className={styles.fileList}>
                  {entryPoints.map(node => (
                    <button type="button" key={node.id} className={styles.fileRow} onClick={() => openNode(node)}>
                      <span className={styles.fileType}>{node.language || "file"}</span>
                      <span>{filenameFor(node.id)}</span>
                      <strong>{folderFor(node.id)}</strong>
                    </button>
                  ))}
                </div>
              ) : (
                <p className={styles.note}>No conventional entry-point filenames were detected.</p>
              )}
            </section>

            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <div><span>04</span><h3>Important files</h3></div>
                <small>ranked by connections and symbols</small>
              </div>
              <div className={styles.fileList}>
                {centralFiles.map((node, index) => (
                  <button type="button" key={node.id} className={styles.fileRow} onClick={() => openNode(node)}>
                    <span className={styles.rank}>0{index + 1}</span>
                    <span>{filenameFor(node.id)}</span>
                    <strong>{(node.num_functions || 0) + (node.num_classes || 0)} symbols</strong>
                  </button>
                ))}
              </div>
            </section>
          </div>
        )}

        {view === "files" && (
          <section className={styles.fullPanel}>
            <div className={styles.panelHeader}>
              <div><span>FILES</span><h3>Repository files</h3></div>
              <small>{visibleNodes.length} shown</small>
            </div>
            <div className={styles.table}>
              {visibleNodes.map(node => (
                <button type="button" key={node.id} className={styles.tableRow} onClick={() => openNode(node)}>
                  <span className={styles.fileType}>{node.language || "file"}</span>
                  <span className={styles.tableName}>{node.id}</span>
                  <span>{node.num_functions || 0} fn</span>
                  <span>{node.num_classes || 0} cls</span>
                  <span className={styles.arrow}>→</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {view === "connections" && (
          <section className={styles.fullPanel}>
            <div className={styles.panelHeader}>
              <div><span>DEPENDENCIES</span><h3>File relationships</h3></div>
              <small>{edges.length} detected</small>
            </div>
            {edges.length ? (
              <div className={styles.connections}>
                {edges.map((edge, index) => (
                  <button
                    type="button"
                    key={`${edge.source}-${edge.target}-${index}`}
                    className={styles.connectionRow}
                    onClick={() => openNode(nodes.find(node => node.id === edge.source))}
                  >
                    <span>{filenameFor(edge.source)}</span>
                    <i>→</i>
                    <span>{filenameFor(edge.target)}</span>
                    <small>
                      <b>{edge.kind || "dependency"}</b>
                      {" · "}
                      {edge.confidence || "high"}
                      {" · "}
                      {edge.label || "relationship"}
                    </small>
                  </button>
                ))}
              </div>
            ) : (
              <div className={styles.noConnections}>
                <span>NO IMPORT EDGES FOUND</span>
                <h3>Dependencies were not detected</h3>
                <p>
                  This can happen for standalone scripts or repositories with unsupported
                  import styles. Use the file view to inspect the project directly.
                </p>
                <div className={styles.connectionStats}>
                  <div><strong>{connectedNodes.length}</strong><span>connected files</span></div>
                  <div><strong>{nodes.length - connectedNodes.length}</strong><span>standalone files</span></div>
                </div>
              </div>
            )}
          </section>
        )}
      </div>

      {selected && (
        <aside className={styles.details}>
          <button className={styles.close} type="button" onClick={() => setSelected(null)} aria-label="Close file details">×</button>
          <span className={styles.detailFolder}>{folderFor(selected.id)}</span>
          <h3>{filenameFor(selected.id)}</h3>
          <div className={styles.detailStats}>
            <span>{selected.num_functions || 0} functions</span>
            <span>{selected.num_classes || 0} classes</span>
          </div>
          <button type="button" className={styles.openSource} onClick={() => onNodeClick?.({
            path: selected.id,
          })}>
            Open source
          </button>
        </aside>
      )}
    </div>
  )
}
