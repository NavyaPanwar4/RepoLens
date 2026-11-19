import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import MarkdownText from "./MarkdownText"

describe("MarkdownText", () => {
  it("renders headings and lists without exposing raw markdown", () => {
    render(<MarkdownText>{"## Architecture\n\n- FastAPI backend\n- React frontend"}</MarkdownText>)

    expect(screen.getByRole("heading", { name: "Architecture" })).toBeInTheDocument()
    expect(screen.getByText("FastAPI backend")).toBeInTheDocument()
    expect(screen.getByText("React frontend")).toBeInTheDocument()
  })

  it("renders inline code", () => {
    render(<MarkdownText>{"Use `python -m uvicorn` to start."}</MarkdownText>)
    expect(screen.getByText("python -m uvicorn")).toBeInTheDocument()
  })
})
