import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import client from "../api/client"
import MarkdownText from "../components/MarkdownText"
import styles from "./SharedWorkspace.module.css"

export default function SharedWorkspace() {
  const { token } = useParams()
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState("")

  useEffect(() => {
    let active = true
    client.get(`/shared/${token}`)
      .then(({ data }) => {
        if (active) setAnalysis(data)
      })
      .catch(err => {
        if (active) setError(err.response?.data?.detail || "Shared workspace is unavailable")
      })
    return () => { active = false }
  }, [token])

  if (error) return <div className={styles.state}>{error}</div>
  if (!analysis) return <div className={styles.state}>Loading shared repository…</div>

  const overview = analysis.overview || {}
  const health = overview.health || {}
  const findings = overview.prioritized_findings || []

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link className={styles.brand} to="/">
          <span>R</span><strong>repolens</strong>
        </Link>
        <span className={styles.readonly}>READ-ONLY SHARE</span>
      </header>
      <div className={styles.content}>
        <section className={styles.hero}>
          <span className={styles.kicker}>REPOSITORY OVERVIEW</span>
          <h1>Shared system intelligence</h1>
        </section>
        <div className={styles.metrics}>
          <div><strong>{analysis.summary?.total_files || 0}</strong><span>files</span></div>
          <div><strong>{overview.dependency_edges || 0}</strong><span>relationships</span></div>
          <div><strong>{health.health_score ?? 0}</strong><span>health score</span></div>
          <div><strong>{findings.length}</strong><span>findings</span></div>
        </div>
        <section className={styles.summary}>
          <div className={styles.sectionHeader}><span>01</span><h2>AI architecture summary</h2></div>
          <MarkdownText>
            {overview.architecture_summary || "No architecture summary was generated."}
          </MarkdownText>
        </section>
        <section className={styles.summary}>
          <div className={styles.sectionHeader}><span>02</span><h2>Prioritized findings</h2></div>
          {findings.length ? (
            <div className={styles.findings}>
              {findings.slice(0, 20).map((finding, index) => (
                <div key={`${finding.file}-${finding.line}-${index}`}>
                  <strong>{finding.severity?.toUpperCase()}</strong>
                  <span>{finding.file}:{finding.line}</span>
                  <p>{finding.message}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className={styles.empty}>No prioritized findings detected.</p>
          )}
        </section>
      </div>
    </main>
  )
}
