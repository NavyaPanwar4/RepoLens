import { useEffect, useState } from "react"
import { Link, useLocation, useParams } from "react-router-dom"
import client from "../api/client"
import ChatMessage from "../components/ChatMessage"
import GraphView from "../components/GraphView"
import SourceExplorer from "../components/SourceExplorer"
import BugPanel from "../components/BugPanel"
import OverviewView from "../components/OverviewView"
import styles from "./Chat.module.css"

export default function Chat() {
  const { repoId } = useParams()
  const location = useLocation()
  const matchingLocationState =
    location.state?.repo_id === repoId ? location.state : null
  const [analysis, setAnalysis] = useState(matchingLocationState)
  const [loading, setLoading] = useState(!matchingLocationState)
  const [error, setError] = useState("")
  const [activeTab, setActiveTab] = useState("overview")
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState("")
  const [asking, setAsking] = useState(false)
  const [selectedFile, setSelectedFile] = useState("")
  const [selectedLine, setSelectedLine] = useState(1)

  useEffect(() => {
    if (location.state?.repo_id === repoId) {
      setAnalysis(location.state)
      setLoading(false)
      return
    }
    let active = true
    client.get(`/repositories/${repoId}`)
      .then(({ data }) => {
        if (active) setAnalysis(data)
      })
      .catch(err => {
        if (active) setError(err.response?.data?.detail || "Unable to load analysis")
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [repoId, location.state])

  useEffect(() => {
    const firstFile = analysis?.graph?.nodes?.[0]?.id
    if (firstFile && !selectedFile) setSelectedFile(firstFile)
  }, [analysis, selectedFile])

  async function askQuestion(text) {
    const nextQuestion = text?.trim() || question.trim()
    if (!nextQuestion || asking) return
    setActiveTab("chat")
    setAsking(true)
    setQuestion("")
    setMessages(current => [...current, { role: "user", text: nextQuestion }])
    try {
      const { data } = await client.post("/ask", {
        repo_id: repoId,
        question: nextQuestion,
        summary: analysis?.summary,
        context: {
          summary: analysis?.summary,
          overview: analysis?.overview,
          graph: analysis?.graph,
        },
      })
      setMessages(current => [...current, {
        role: "assistant",
        text: data.answer,
        chunks: data.context_chunks,
      }])
    } catch (err) {
      setMessages(current => [...current, {
        role: "assistant",
        text: err.response?.data?.detail || "Unable to answer that question.",
        isError: true,
      }])
    } finally {
      setAsking(false)
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    askQuestion()
  }

  function openSource(file, line = 1) {
    setSelectedFile(file)
    setSelectedLine(line)
    setActiveTab("source")
  }

  if (loading) return <div className={styles.loading}>Loading analysis workspace…</div>
  if (error) return <div className={styles.error}>{error}</div>
  if (!analysis) return null

  const files = analysis.graph?.nodes || []

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link className={styles.brand} to="/">
          <span className={styles.brandMark}>R</span>
          <span>repolens</span>
        </Link>
        <div className={styles.stats}>
          <span>{analysis.summary?.total_files || files.length} files</span>
          <span>{analysis.summary?.total_edges || 0} relationships</span>
          <span>{analysis.chunks_stored || 0} indexed chunks</span>
        </div>
      </header>

      <div className={styles.body}>
        <nav className={styles.sidebar} aria-label="Analysis views">
          {[
            ["overview", "Overview", "01"],
            ["chat", "Chat", "02"],
            ["graph", "Architecture", "03"],
            ["source", "Source", "04"],
            ["bugs", "Issues", "05"],
          ].map(([tab, label, number]) => (
            <button
              key={tab}
              type="button"
              className={`${styles.tab} ${activeTab === tab ? styles.tabActive : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              <span>{number}</span>{label}
            </button>
          ))}
        </nav>

        <main className={styles.main}>
          {activeTab === "overview" && (
            <OverviewView
              repoId={repoId}
              onOpenSource={openSource}
              onOpenArchitecture={() => setActiveTab("graph")}
            />
          )}

          {activeTab === "chat" && (
            <section className={styles.chat}>
              <div className={styles.messages}>
                {messages.length === 0 ? (
                  <div className={styles.emptyChat}>
                    <span className={styles.emptyEyebrow}>REPOSITORY ASSISTANT</span>
                    <strong>What would you like to understand?</strong>
                    <p>Questions are answered with citations from the indexed source code.</p>
                    <div className={styles.suggestions}>
                      {[
                        "Explain the overall architecture",
                        "Which files are the main entry points?",
                        "Summarize the main risks",
                      ].map(prompt => (
                        <button key={prompt} type="button" onClick={() => askQuestion(prompt)}>
                          {prompt}<span>→</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : messages.map((message, index) => (
                  <ChatMessage
                    key={index}
                    message={message}
                    onOpenSource={openSource}
                  />
                ))}
              </div>
              <form className={styles.composer} onSubmit={handleSubmit}>
                <input
                  className={styles.input}
                  value={question}
                  onChange={event => setQuestion(event.target.value)}
                  placeholder="Ask about architecture, code, or risks…"
                  aria-label="Question"
                />
                <button className={styles.send} type="submit" disabled={asking || !question.trim()}>
                  {asking ? "Thinking…" : "Send"}
                </button>
              </form>
            </section>
          )}

          {activeTab === "graph" && (
            <GraphView
              graphData={analysis.graph}
              onNodeClick={node => openSource(node.path, 1)}
            />
          )}

          {activeTab === "source" && (
            <SourceExplorer
              repoId={repoId}
              files={files}
              selectedFile={selectedFile}
              selectedLine={selectedLine}
              onSelectFile={(file, line) => { setSelectedFile(file); setSelectedLine(line) }}
              onAskAboutFile={file => askQuestion(`Explain the purpose and behavior of ${file}.`)}
            />
          )}

          {activeTab === "bugs" && (
            <BugPanel
              bugs={analysis.bugs}
              onAskAboutBug={finding => askQuestion(
                `Explain this issue and suggest a fix: ${finding.rule} in ${finding.file}:${finding.line}: ${finding.message}`
              )}
            />
          )}
        </main>
      </div>
    </div>
  )
}
