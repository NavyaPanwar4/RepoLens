import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import client from "../api/client"
import styles from "./Compare.module.css"

export default function Compare() {
  const [repositories, setRepositories] = useState([])
  const [selected, setSelected] = useState([])
  const [comparison, setComparison] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    let active = true
    client.get("/repositories", { params: { limit: 100 } })
      .then(({ data }) => {
        if (active) setRepositories(data.repositories || [])
      })
      .catch(() => {
        if (active) setRepositories([])
      })
    return () => { active = false }
  }, [])

  function toggle(repoId) {
    setSelected(current => {
      if (current.includes(repoId)) return current.filter(id => id !== repoId)
      if (current.length >= 5) return current
      return [...current, repoId]
    })
  }

  async function runComparison() {
    if (selected.length < 2) return
    setLoading(true)
    setError("")
    try {
      const { data } = await client.post("/repositories/compare", { repo_ids: selected })
      setComparison(data)
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to compare repositories")
    } finally {
      setLoading(false)
    }
  }

  async function downloadReport() {
    const response = await client.post(
      "/repositories/compare/report",
      { repo_ids: selected },
      { responseType: "blob" },
    )
    const url = URL.createObjectURL(response.data)
    const link = document.createElement("a")
    link.href = url
    link.download = "repository-comparison.md"
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link className={styles.brand} to="/"><span>R</span><strong>repolens</strong></Link>
        <span className={styles.kicker}>MULTI-REPOSITORY ANALYSIS</span>
      </header>

      <div className={styles.content}>
        <section className={styles.intro}>
          <div>
            <span className={styles.sectionLabel}>COMPARISON WORKSPACE</span>
            <h1>Compare codebases.</h1>
          </div>
          <p>Select two to five saved repositories, then compare health, scale, relationships, and findings.</p>
        </section>

        <section className={styles.selector}>
          <div className={styles.selectorHeader}>
            <h2>Repositories</h2>
            <span>{selected.length}/5 selected</span>
          </div>
          <div className={styles.repositoryList}>
            {repositories.map(repository => (
              <button
                type="button"
                key={repository.repo_id}
                className={selected.includes(repository.repo_id) ? styles.selected : styles.repository}
                onClick={() => toggle(repository.repo_id)}
              >
                <span className={styles.check}>{selected.includes(repository.repo_id) ? "✓" : "+"}</span>
                <span>
                  <strong>{repository.source_url || repository.repo_id.slice(0, 16)}</strong>
                  <small>{repository.summary?.total_files || 0} files · {repository.bugs?.total || 0} findings</small>
                </span>
              </button>
            ))}
            {repositories.length === 0 && <p className={styles.empty}>No saved repositories are available.</p>}
          </div>
          {error && <p className={styles.error}>{error}</p>}
          <button
            type="button"
            className={styles.compareButton}
            disabled={selected.length < 2 || loading}
            onClick={runComparison}
          >
            {loading ? "Comparing…" : "Compare repositories"}
          </button>
        </section>

        {comparison && (
          <section className={styles.results}>
            <div className={styles.resultsHeader}>
              <div>
                <span className={styles.sectionLabel}>COMPARISON RESULTS</span>
                <h2>{comparison.summary.repository_count} repositories</h2>
              </div>
              <button type="button" onClick={downloadReport}>Download report</button>
            </div>

            <div className={styles.summaryGrid}>
              <div><span>Strongest health</span><strong>{comparison.summary.strongest_health?.slice(0, 12)}</strong></div>
              <div><span>Largest repository</span><strong>{comparison.summary.largest_repository?.slice(0, 12)}</strong></div>
              <div><span>Common findings</span><strong>{comparison.summary.common_finding_count}</strong></div>
              <div><span>Unique findings</span><strong>{comparison.summary.unique_finding_count}</strong></div>
            </div>

            <div className={styles.table}>
              <div className={styles.tableHeader}>
                <span>Repository</span><span>Files</span><span>Relationships</span><span>Calls</span><span>Health</span><span>Findings</span>
              </div>
              {comparison.repositories.map(repository => (
                <div className={styles.tableRow} key={repository.repo_id}>
                  <Link to={`/chat/${repository.repo_id}`}>{repository.source_url || repository.repo_id.slice(0, 16)}</Link>
                  <span>{repository.files}</span>
                  <span>{repository.relationships}</span>
                  <span>{repository.call_edges}</span>
                  <strong>{repository.health_score}</strong>
                  <span>{repository.errors} E · {repository.warnings} W · {repository.info} I</span>
                </div>
              ))}
            </div>

            <div className={styles.findingsGrid}>
              <section>
                <h3>Common findings</h3>
                {comparison.common_findings.length ? comparison.common_findings.slice(0, 12).map((finding, index) => (
                  <div key={`${finding.rule}-${finding.file}-${index}`}>
                    <strong>{finding.rule}</strong>
                    <span>{finding.file}:{finding.line}</span>
                  </div>
                )) : <p>No findings are common to every selected repository.</p>}
              </section>
              <section>
                <h3>Repository-specific findings</h3>
                {comparison.unique_findings.length ? comparison.unique_findings.slice(0, 12).map((finding, index) => (
                  <div key={`${finding.rule}-${finding.file}-${index}`}>
                    <strong>{finding.rule}</strong>
                    <span>{finding.repositories.join(", ")}</span>
                  </div>
                )) : <p>No repository-specific findings were found.</p>}
              </section>
            </div>
          </section>
        )}
      </div>
    </main>
  )
}
