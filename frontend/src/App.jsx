import { Routes, Route } from "react-router-dom"
import Home from "./pages/Home"
import Chat from "./pages/Chat"
import SharedWorkspace from "./pages/SharedWorkspace"
import Compare from "./pages/Compare"

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/chat/:repoId" element={<Chat />} />
      <Route path="/shared/:token" element={<SharedWorkspace />} />
      <Route path="/compare" element={<Compare />} />
    </Routes>
  )
}