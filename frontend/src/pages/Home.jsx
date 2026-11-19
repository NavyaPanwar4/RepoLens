import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import client from "../api/client"
import styles from "./Home.module.css"

const analysisSteps = ["Clone or unpack", "Map the system", "Index evidence", "Surface risks"]

export default function Home() {
  const [tab, setTab] = useState("url")
  const [url, setUrl] = useState("")
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [status, setStatus] = useState("")
  const [jobId, setJobId] = useState("")
  const [recent, setRecent] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    client.get("/repositories")
      .then(({ data }) => {
        if (active) setRecent(data.repositories || [])
      })
      .catch(() => {
        if (active) setRecent([])
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!jobId) return
    let timeout
    let active = true
    async function pollJob() {
      try {
        const { data } = await client.get(`/ingest/jobs/${jobId}`)
        if (!active) return
        setStatus(data.phase)
        if (data.status === "completed") {
          navigate(`/chat/${data.result.repo_id}`, { state: data.result })
          return
        }
        if (data.status === "failed") {
          setError(data.error || "Analysis failed")
          setLoading(false)
          setJobId("")
          return
        }
        timeout = setTimeout(pollJob, 800)
      } catch (err) {
        if (!active) return
        setError(err.response?.data?.detail || "Unable to check analysis progress")
        setLoading(false)
        setJobId("")
      }
    }
    pollJob()
    return () => { active = false; clearTimeout(timeout) }
  }, [jobId, navigate])

  async function handleSubmit(event) {
    event.preventDefault()
    setError("")
    setLoading(true)
    try {
      let response
      if (tab === "url") {
        setStatus("Queueing repository analysis…")
        response = await client.post("/ingest/url", { url })
      } else {
        setStatus("Uploading ZIP archive…")
        const form = new FormData()
        form.append("file", file)
        response = await client.post("/ingest/zip", form)
      }
      setJobId(response.data.job_id)
      setStatus(response.data.phase)
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong")
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.aurora} />
      <nav className={styles.nav}>
        <div className={styles.brand}><span className={styles.brandMark}>R</span><span>repolens</span></div>
        <div className={styles.navMeta}>
          <button type="button" className={styles.compareLink} onClick={() => navigate("/compare")}>Compare repositories</button>
          <span className={styles.statusDot} /> Evidence-first code intelligence
        </div>
      </nav>

      <main className={styles.main}>
        <section className={styles.hero}>
          <div className={styles.copy}>
            <div className={styles.eyebrow}><span /> Your codebase, in focus</div>
            <h1>See the shape of<br /><em>any codebase.</em></h1>
            <p className={styles.lede}>Turn an unfamiliar repository into an explainable architecture, searchable evidence, and a clear first move.</p>
            <div className={styles.trustRow}>
              <div><strong>01</strong><span>Architecture map</span></div>
              <div><strong>02</strong><span>Grounded answers</span></div>
              <div><strong>03</strong><span>Risk signals</span></div>
            </div>
          </div>

          <div className={styles.launchCard}>
            <div className={styles.cardTopline}><span>NEW ANALYSIS</span><span>v0.2</span></div>
            <h2>Start with the source.</h2>
            <p>Connect a public GitHub repository or upload a project archive.</p>
            <div className={styles.tabs} role="tablist" aria-label="Input method">
              <button type="button" className={tab === "url" ? styles.active : ""} onClick={() => setTab("url")}>GitHub repository</button>
              <button type="button" className={tab === "zip" ? styles.active : ""} onClick={() => setTab("zip")}>ZIP archive</button>
            </div>
            <form onSubmit={handleSubmit} className={styles.form}>
              {tab === "url" ? (
                <label className={styles.inputShell}><span>↗</span><input type="url" placeholder="https://github.com/owner/repository" value={url} onChange={event => setUrl(event.target.value)} required /></label>
              ) : (
                <label className={styles.fileLabel}><input type="file" accept=".zip" onChange={event => setFile(event.target.files[0])} required /><span className={styles.uploadIcon}>↑</span><span>{file ? file.name : "Choose a project ZIP"}</span><small>Up to 100 MB</small></label>
              )}
              <button className={styles.launchButton} type="submit" disabled={loading}><span>{loading ? "Analysis in progress" : "Analyze repository"}</span><b>→</b></button>
            </form>
            {loading && status && <div className={styles.progress}><span className={styles.spinner} />{status}</div>}
            {error && <p className={styles.error}>{error}</p>}
            <p className={styles.privacy}>Public GitHub repositories only · Source snapshots remain in your local workspace</p>
          </div>
        </section>

        {recent.length > 0 && (
          <section className={styles.recentSection}>
            <div className={styles.recentHeader}>
              <div><span className={styles.sectionLabel}>RECENT WORKSPACES</span><h2>Continue an analysis.</h2></div>
            </div>
            <div className={styles.recentList}>
              {recent.slice(0, 4).map(item => (
                <button
                  type="button"
                  key={item.repo_id}
                  className={styles.recentCard}
                  onClick={() => navigate(`/chat/${item.repo_id}`)}
                >
                  <div>
                    <span>WORKSPACE</span>
                    <strong>{item.repo_id.slice(0, 12)}</strong>
                  </div>
                  <div>
                    <span>{item.summary?.total_files || 0} files</span>
                    <span>{item.bugs?.total || 0} findings</span>
                  </div>
                  <b>Open →</b>
                </button>
              ))}
            </div>
          </section>
        )}

        <section className={styles.previewSection}>
          <div className={styles.previewCopy}><span className={styles.sectionLabel}>A CLARITY LAYER FOR CODE</span><h2>From file tree to<br />shared understanding.</h2><p>Navigate the system visually, inspect the exact evidence behind an answer, then decide what to do next.</p></div>
          <div className={styles.mapCard} aria-label="Example architecture map">
            <div className={styles.mapHeader}><span>ARCHITECTURE</span><span className={styles.live}>● LIVE MAP</span></div>
            <div className={styles.mapBody}>
              <div className={`${styles.mapNode} ${styles.primary}`}>app/main.py <small>entry point</small></div>
              <div className={`${styles.mapNode} ${styles.left}`}>routes/ <small>API surface</small></div>
              <div className={`${styles.mapNode} ${styles.right}`}>services/ <small>domain logic</small></div>
              <div className={`${styles.mapNode} ${styles.bottom}`}>vector store <small>evidence layer</small></div>
              <i className={`${styles.line} ${styles.lineOne}`} /><i className={`${styles.line} ${styles.lineTwo}`} /><i className={`${styles.line} ${styles.lineThree}`} />
            </div>
            <div className={styles.mapFooter}><span>42 files mapped</span><span>18 relationships traced</span></div>
          </div>
        </section>

        <section className={styles.process}>
          {analysisSteps.map((step, index) => <div className={styles.processItem} key={step}><span>0{index + 1}</span><p>{step}</p></div>)}
        </section>
      </main>
    </div>
  )
}
