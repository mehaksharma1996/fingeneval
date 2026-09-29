import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import App from "./App";

describe("FinGenEval Enterprise shell", () => {
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
});
