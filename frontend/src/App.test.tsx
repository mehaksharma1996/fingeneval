import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import App, { SystemVersionCard } from "./App";
import type { SystemVersion } from "./types";

const baseline: SystemVersion = {
  id: "system-1",
  project_id: "project-1",
  name: "AML Assistant",
  version: "1.0-baseline",
  kind: "BASELINE",
  model_provider: "deterministic-local",
  model_name: "fingeneval-fixture",
  prompt_version_id: "prompt-1",
  prompt_version: "strict-governance/1",
  retrieval_configuration_id: "retrieval-1",
  retrieval_config: { method: "bm25", top_k: 3 },
  tool_config: { filing_tool: "disabled" },
  data_source_version: "aml-policy/1.0",
  created_at: "2026-01-01T00:00:00Z",
};

describe("FinGenEval governance prototype shell", () => {
  beforeEach(() => localStorage.clear());

  it("labels the credential-free demo as synthetic", () => {
    render(<App />);
    expect(
      screen.getByText("Can this financial AI system be released?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Synthetic data only")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Load synthetic AML workspace" }),
    ).toBeEnabled();
  });

  it("renders persisted system configuration without hard-coded retrieval labels", () => {
    const { rerender } = render(
      <SystemVersionCard label="Production baseline" system={baseline} />,
    );
    expect(screen.getByText("BM25 · top 3")).toBeInTheDocument();
    expect(
      screen.getByText("deterministic-local / fingeneval-fixture"),
    ).toBeInTheDocument();
    expect(screen.getByText("strict-governance/1")).toBeInTheDocument();
    expect(screen.getByText("filing tool: disabled")).toBeInTheDocument();
    expect(screen.getByText("aml-policy/1.0")).toBeInTheDocument();

    rerender(
      <SystemVersionCard
        label="Production baseline"
        system={{
          ...baseline,
          retrieval_config: { method: "vector", top_k: 5 },
        }}
      />,
    );
    expect(screen.getByText("VECTOR · top 5")).toBeInTheDocument();
    expect(screen.queryByText("BM25 · top 3")).not.toBeInTheDocument();
  });
});
