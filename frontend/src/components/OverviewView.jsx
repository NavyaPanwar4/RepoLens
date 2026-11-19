import { useEffect, useState } from "react"
import client from "../api/client"
import MarkdownText from "./MarkdownText"
import styles from "./OverviewView.module.css"

export default function OverviewView({ repoId, onOpenSource, onOpenArchitecture }) {
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [git, setGit] = useState(null)
  const [pullRequests, setPullRequests] = useState([])
  const [shareUrl, setShareUrl] = useState("")
  const [scannerStatus, setScannerStatus] = useState(null)

  useEffect(() => {
    let active = true
    client.get(`/repositories/${repoId}/overview`)
      .then(({ data }) => {
        if (active) setOverview(data)
      })
      .catch(err => {
        if (active) setError(err.response?.data?.detail || "Unable to load repository overview")
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    client.get(`/repositories/${repoId}/git`)
      .then(({ data }) => {
        if (active) setGit(data)
      })
      .catch(() => {
        if (active) setGit(null)
      })
    client.get(`/repositories/${repoId}/pulls`)
      .then(({ data }) => {
        if (active) setPullRequests(data.pull_requests || [])
      })
      .catch(() => {
        if (active) setPullRequests([])
      })
    return () => { active = false }
  }, [repoId])

  async function downloadReport() {
    const response = await client.get(`/repositories/${repoId}/report`, { responseType: "blob" })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement("a")
    link.href = url
    link.download = `${repoId}-report.md`
    link.click()
    URL.revokeObjectURL(url)
  }

  async function downloadPdf() {
    const response = await client.get(`/repositories/${repoId}/report.pdf`, { responseType: "blob" })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement("a")
    link.href = url
    link.download = `${repoId}-report.pdf`
    link.click()
    URL.revokeObjectURL(url)
  }

  async function createShare() {
    const { data } = await client.post(`/repositories/${repoId}/share`)
    const url = `${window.location.origin}/shared/${data.token}`
    setShareUrl(url)
  }

  async function revokeShare() {
    await client.delete(`/repositories/${repoId}/share`)
    setShareUrl("")
  }

  async function copyShare() {
    if (shareUrl) await navigator.clipboard.writeText(shareUrl)
  }

  async function deleteWorkspace() {
    if (!window.confirm("Delete this repository analysis and its stored source snapshot?")) return
    await client.delete(`/repositories/${repoId}`)
    window.location.href = "/"
  }

  async function runScanners() {
    setScannerStatus({ enabled: true, running: true })
    try {
      const { data } = await client.post(`/repositories/${repoId}/scan`)
      setScannerStatus({ ...data, running: false })
    } catch (err) {
      setScannerStatus({
        running: false,
        enabled: true,
        messages: [err.response?.data?.detail || "Scanner run failed"],
      })
    }
  }

  if (loading) return <div className={styles.loading}>Building repository overview…</div>
  if (error) return <div className={styles.error}>{error}</div>
  if (!overview) return null

  const health = overview.health || {}
  const testing = overview.testing || {}
  const coverage = testing.coverage || {}
  const findings = overview.prioritized_findings || []
  const severityCounts = {
    error: health.errors || 0,
    warning: health.warnings || 0,
    info: health.info || 0,
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>REPOSITORY OVERVIEW</span>
          <h2>System intelligence</h2>
        </div>
        <button type="button" className={styles.exportButton} onClick={downloadReport}>
          Export report
        </button>
      </header>

      <div className={styles.grid}>
        <section className={`${styles.card} ${styles.summary}`}>
          <div className={styles.cardHeader}>
            <span>01</span>
            <h3>AI architecture summary</h3>
          </div>
          <div className={styles.summaryText}>
            <MarkdownText>
              {overview.architecture_summary || "No architecture summary was generated."}
            </MarkdownText>
          </div>
        </section>

        <section className={`${styles.card} ${styles.health}`}>
          <div className={styles.cardHeader}>
            <span>02</span>
            <h3>Code health</h3>
          </div>
          <div className={styles.score}>
            <strong>{health.health_score ?? 0}</strong>
            <span>/ 100</span>
          </div>
          <div className={styles.healthGrid}>
            <div><strong>{health.total_lines || 0}</strong><span>lines</span></div>
            <div><strong>{health.long_functions || 0}</strong><span>long functions</span></div>
            <div><strong>{health.todo_count || 0}</strong><span>TODO markers</span></div>
          </div>
        </section>

        <section className={`${styles.card} ${styles.stack}`}>
          <div className={styles.cardHeader}>
            <span>03</span>
            <h3>Technology stack</h3>
          </div>
          <div className={styles.badges}>
            {(overview.frameworks || []).map(framework => (
              <span className={styles.framework} key={framework}>{framework}</span>
            ))}
            {Object.entries(overview.languages || {}).map(([language, count]) => (
              <span key={language}>{language}<strong>{count}</strong></span>
            ))}
          </div>
        </section>

        <section className={`${styles.card} ${styles.dependencies}`}>
          <div className={styles.cardHeader}>
            <span>04</span>
            <h3>Dependency analysis</h3>
            <button type="button" onClick={onOpenArchitecture}>View map</button>
          </div>
          <div className={styles.dependencyStats}>
            <div><strong>{overview.dependency_edges || 0}</strong><span>relationships</span></div>
            <div><strong>{overview.call_edges || 0}</strong><span>symbol calls</span></div>
            <div><strong>{health.connected_files || 0}</strong><span>connected files</span></div>
            <div><strong>{health.standalone_files || 0}</strong><span>standalone files</span></div>
          </div>
        </section>

        <section className={`${styles.card} ${styles.entryPoints}`}>
          <div className={styles.cardHeader}>
            <span>05</span>
            <h3>Entry points</h3>
          </div>
          <div className={styles.fileList}>
            {(overview.entry_points || []).slice(0, 6).map(path => (
              <button type="button" key={path} onClick={() => onOpenSource(path, 1)}>
                <span>{path}</span><b>Open →</b>
              </button>
            ))}
            {(overview.entry_points || []).length === 0 && (
              <p>No conventional entry-point files were detected.</p>
            )}
          </div>
        </section>

        <section className={`${styles.card} ${styles.findings}`}>
          <div className={styles.cardHeader}>
            <span>06</span>
            <h3>Prioritized findings</h3>
          </div>
          <div className={styles.severityRow}>
            {Object.entries(severityCounts).map(([severity, count]) => (
              <div key={severity} className={styles[severity]}><strong>{count}</strong><span>{severity}</span></div>
            ))}
          </div>
          <div className={styles.findingList}>
            {findings.slice(0, 8).map((finding, index) => (
              <button
                type="button"
                key={`${finding.file}-${finding.line}-${index}`}
                onClick={() => onOpenSource(finding.file, finding.line)}
              >
                <span className={`${styles.severityDot} ${styles[finding.severity]}`} />
                <span className={styles.findingText}>
                  <strong>{finding.rule}</strong>
                  <small>{finding.file}:{finding.line}</small>
                </span>
                <b>→</b>
              </button>
            ))}
            {findings.length === 0 && <p>No prioritized findings detected.</p>}
          </div>
        </section>

        <section className={`${styles.card} ${styles.testingCard}`}>
          <div className={styles.cardHeader}>
            <span>07</span>
            <h3>Tests and coverage</h3>
          </div>
          <div className={styles.testingStats}>
            <div>
              <strong>{coverage.line_percent == null ? "N/A" : `${coverage.line_percent}%`}</strong>
              <span>line coverage</span>
            </div>
            <div>
              <strong>{testing.test_file_count || 0}</strong>
              <span>test files</span>
            </div>
            <div>
              <strong>{testing.untested_file_count || 0}</strong>
              <span>likely untested</span>
            </div>
          </div>
          <div className={styles.testingDetails}>
            <div>
              <span>Frameworks</span>
              <strong>{(testing.frameworks || []).join(", ") || "Not detected"}</strong>
            </div>
            <div>
              <span>Coverage report</span>
              <strong>{coverage.available ? coverage.format : "No report detected"}</strong>
            </div>
            <div>
              <span>Test/source ratio</span>
              <strong>{testing.test_source_ratio || 0}</strong>
            </div>
          </div>
          {(testing.untested_files || []).length > 0 && (
            <div className={styles.untestedList}>
              {(testing.untested_files || []).slice(0, 6).map(path => (
                <button type="button" key={path} onClick={() => onOpenSource(path, 1)}>
                  <span>{path}</span><b>Open →</b>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className={`${styles.card} ${styles.central}`}>
          <div className={styles.cardHeader}>
            <span>08</span>
            <h3>Central files</h3>
          </div>
          <div className={styles.centralList}>
            {(overview.central_files || []).slice(0, 8).map((file, index) => (
              <button type="button" key={file.path} onClick={() => onOpenSource(file.path, 1)}>
                <span>0{index + 1}</span>
                <strong>{file.path}</strong>
                <small>{file.functions} fn · {file.classes} cls</small>
              </button>
            ))}
          </div>
        </section>

        <section className={`${styles.card} ${styles.git}`}>
          <div className={styles.cardHeader}>
            <span>09</span>
            <h3>Git history</h3>
          </div>
          {git?.commits?.length ? (
            <div className={styles.commitList}>
              {git.commits.slice(0, 8).map(commit => (
                <div key={commit.sha}>
                  <code>{commit.short_sha}</code>
                  <span>
                    <strong>{commit.subject}</strong>
                    <small>{commit.author} · {commit.changed_files} files</small>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className={styles.gitEmpty}>No Git history was available for this archive.</p>
          )}
        </section>

        <section className={`${styles.card} ${styles.actions}`}>
          <div className={styles.cardHeader}>
            <span>10</span>
            <h3>Workspace</h3>
          </div>
          <div className={styles.actionButtons}>
            <button type="button" onClick={downloadReport}>Download Markdown</button>
            <button type="button" onClick={downloadPdf}>Download PDF</button>
            {shareUrl ? (
              <>
                <button type="button" onClick={copyShare}>Copy share link</button>
                <button type="button" className={styles.danger} onClick={revokeShare}>Revoke share link</button>
              </>
            ) : (
              <button type="button" onClick={createShare}>Create share link</button>
            )}
            <button type="button" onClick={runScanners}>
              {scannerStatus?.running ? "Scanning…" : "Run security scanners"}
            </button>
            <button type="button" className={styles.danger} onClick={deleteWorkspace}>Delete workspace</button>
          </div>
          {(scannerStatus || overview.scanners) && (
            <div className={styles.scannerStatus}>
              {(scannerStatus?.messages || overview.scanners?.messages || []).map(message => (
                <p key={message}>{message}</p>
              ))}
            </div>
          )}
        </section>

        {pullRequests.length > 0 && (
          <section className={`${styles.card} ${styles.central}`}>
            <div className={styles.cardHeader}>
              <span>10</span>
              <h3>Open pull requests</h3>
            </div>
            <div className={styles.commitList}>
              {pullRequests.slice(0, 8).map(pr => (
                <a
                  key={pr.number}
                  href={pr.url}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.pullRequest}
                >
                  <code>#{pr.number}</code>
                  <span>
                    <strong>{pr.title}</strong>
                    <small>{pr.author} · {pr.head} → {pr.base}</small>
                  </span>
                </a>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
