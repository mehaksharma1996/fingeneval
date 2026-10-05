import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type {
  Dashboard,
  DemoContext,
  Finding,
  RunDetail,
  SystemVersion,
} from "./types";

const views = [
  "Dashboard",
  "Project setup",
  "System registry",
  "Dataset",
  "Evaluation run",
  "Finding detail",
  "Release decision",
  "Report & handoff",
];

function Pill({ value }: { value: string }) {
  const tone =
    value.includes("BLOCK") || value === "CRITICAL" || value === "FAIL"
      ? "danger"
      : value.includes("PASS") || value === "COMPLETE"
        ? "success"
        : "neutral";
  return <span className={`pill ${tone}`}>{value.replaceAll("_", " ")}</span>;
}

function Empty({ children }: { children: string }) {
  return <div className="empty">{children}</div>;
}

function displayMethod(method?: string) {
  return method ? method.replaceAll("_", " ").toUpperCase() : "Not configured";
}

function displayTools(tools: Record<string, unknown>) {
  const entries = Object.entries(tools);
  if (!entries.length) return "None";
  return entries
    .map(([name, value]) => `${name.replaceAll("_", " ")}: ${String(value)}`)
    .join(", ");
}

export function SystemVersionCard({
  label,
  system,
  candidate = false,
}: {
  label: string;
  system?: SystemVersion;
  candidate?: boolean;
}) {
  if (!system) {
    return (
      <Empty>{`No registered ${label.toLowerCase()} is available.`}</Empty>
    );
  }
  const topK = system.retrieval_config.top_k;
  return (
    <article className={`panel${candidate ? " candidate" : ""}`}>
      <span className="eyebrow">{label}</span>
      <h2>
        {system.name} {system.version}
      </h2>
      <dl>
        <dt>Provider</dt>
        <dd>
          {system.model_provider} / {system.model_name}
        </dd>
        <dt>Prompt</dt>
        <dd>{system.prompt_version}</dd>
        <dt>Retriever</dt>
        <dd>
          {displayMethod(system.retrieval_config.method)}
          {topK === undefined ? "" : ` · top ${topK}`}
        </dd>
        <dt>Tools</dt>
        <dd>{displayTools(system.tool_config)}</dd>
        <dt>Data source</dt>
        <dd>{system.data_source_version}</dd>
      </dl>
    </article>
  );
}

export default function App() {
  const [view, setView] = useState("Dashboard");
  const [context, setContext] = useState<DemoContext | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<{
    object_key: string;
    content_sha256: string;
  } | null>(null);
  const evaluator = context?.users.EVALUATOR;
  const reviewer = context?.users.COMPLIANCE_REVIEWER;

  async function loadDashboard(ctx = context) {
    if (!ctx) return;
    const data = await api.dashboard(ctx.users.EVALUATOR);
    setDashboard(data);
  }

  async function bootstrap() {
    setBusy(true);
    setError("");
    try {
      const ctx = await api.bootstrap();
      setContext(ctx);
      localStorage.setItem("fingeneval-demo", JSON.stringify(ctx));
      await loadDashboard(ctx);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const saved = localStorage.getItem("fingeneval-demo");
    if (saved) {
      const ctx = JSON.parse(saved) as DemoContext;
      setContext(ctx);
      api
        .dashboard(ctx.users.EVALUATOR)
        .then(setDashboard)
        .catch(() => localStorage.removeItem("fingeneval-demo"));
    }
  }, []);

  async function runEvaluation() {
    if (!context || !evaluator) return;
    setBusy(true);
    setError("");
    try {
      const run = await api.createRun(context.project_id, evaluator);
      const result = await api.run(run.id, evaluator);
      setDetail(result);
      setSelectedFinding(result.findings[0] ?? null);
      await loadDashboard();
      setView("Evaluation run");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function override() {
    if (!detail?.decision || !reviewer) return;
    setBusy(true);
    try {
      await api.review(
        detail.decision.id,
        reviewer,
        "OVERRIDE",
        "Time-limited synthetic demo override with monitoring, ownership, and documented rollback.",
      );
      setDetail(await api.run(detail.run.id, evaluator!));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remediate() {
    if (!selectedFinding || !evaluator) return;
    setBusy(true);
    try {
      const result = await api.remediate(
        selectedFinding.id,
        evaluator,
        evaluator,
      );
      setDetail(await api.run(result.rerun.id, evaluator));
      setSelectedFinding(null);
      setView("Release decision");
      await loadDashboard();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function generateReport() {
    if (!detail || !evaluator) return;
    setBusy(true);
    try {
      setReport(await api.report(detail.run.id, evaluator));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const project = dashboard?.projects[0];
  const baselineSystem = dashboard?.system_versions.find(
    (system) => system.kind === "BASELINE",
  );
  const candidateSystem = dashboard?.system_versions.find(
    (system) => system.kind === "CANDIDATE",
  );
  const regressions = useMemo(
    () => detail?.case_results.filter((item) => item.regression) ?? [],
    [detail],
  );

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <div className="mark">FG</div>
          <div>
            <strong>FinGenEval</strong>
            <small>Governance prototype</small>
          </div>
        </div>
        <nav aria-label="Product navigation">
          {views.map((item) => (
            <button
              className={view === item ? "active" : ""}
              onClick={() => setView(item)}
              key={item}
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="scope">
          <span className="eyebrow">Environment</span>
          <strong>Local development</strong>
          <small>Synthetic data only</small>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">Release assurance workspace</span>
            <h1>{view}</h1>
          </div>
          <div className="header-actions">
            <Pill value="SYNTHETIC" />
            {context && <span className="user">Demo evaluator</span>}
          </div>
        </header>
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}
        {!context ? (
          <section className="welcome">
            <span className="eyebrow">Credential-free guided demo</span>
            <h2>Can this financial AI system be released?</h2>
            <p>
              Load a synthetic AML assistant, compare its baseline and
              candidate, expose a critical deadline regression, and follow the
              evidence through remediation.
            </p>
            <button className="primary" onClick={bootstrap} disabled={busy}>
              {busy ? "Preparing…" : "Load synthetic AML workspace"}
            </button>
          </section>
        ) : null}

        {context && view === "Dashboard" && (
          <>
            <div className="metrics">
              <article>
                <span>Release status</span>
                <strong>
                  {detail?.decision ? (
                    <Pill value={detail.decision.effective_outcome} />
                  ) : (
                    "Not evaluated"
                  )}
                </strong>
              </article>
              <article>
                <span>Open critical findings</span>
                <strong>{dashboard?.open_critical_findings ?? 0}</strong>
              </article>
              <article>
                <span>Recent runs</span>
                <strong>{dashboard?.recent_runs.length ?? 0}</strong>
              </article>
              <article>
                <span>Operational health</span>
                <strong className="health">
                  ● {dashboard?.operational_health ?? "Checking"}
                </strong>
              </article>
            </div>
            <section className="panel hero">
              <div>
                <span className="eyebrow">Pending validation</span>
                <h2>AML Policy Assistant v2.0</h2>
                <p>
                  Candidate changes the prompt while retaining the approved
                  synthetic AML policy source. The release gate will compare it
                  with v1.0.
                </p>
              </div>
              <button
                className="primary"
                onClick={runEvaluation}
                disabled={busy}
              >
                {busy ? "Evaluating…" : "Start baseline comparison"}
              </button>
            </section>
            <section className="panel">
              <div className="section-title">
                <div>
                  <span className="eyebrow">Recent activity</span>
                  <h2>Evaluation runs</h2>
                </div>
              </div>
              {dashboard?.recent_runs.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Status</th>
                      <th>Stage</th>
                      <th>Progress</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.recent_runs.map((run) => (
                      <tr
                        key={run.id}
                        onClick={async () => {
                          setDetail(await api.run(run.id, evaluator!));
                          setView("Evaluation run");
                        }}
                      >
                        <td className="mono">{run.id.slice(0, 8)}</td>
                        <td>
                          <Pill value={run.status} />
                        </td>
                        <td>{run.stage.replaceAll("_", " ")}</td>
                        <td>{run.progress_percent}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <Empty>No evaluation runs yet.</Empty>
              )}
            </section>
          </>
        )}

        {context && view === "Project setup" && (
          <section className="panel detail-grid">
            <div>
              <span className="label">Project</span>
              <h2>{project?.name}</h2>
              <p>{project?.intended_use}</p>
            </div>
            <dl>
              <dt>Risk tier</dt>
              <dd>
                <Pill value={project?.risk_tier ?? "—"} />
              </dd>
              <dt>Business owner</dt>
              <dd>{project?.business_owner}</dd>
              <dt>Technical owner</dt>
              <dd>{project?.technical_owner}</dd>
              <dt>Required approver</dt>
              <dd>{project?.required_approver_roles.join(", ")}</dd>
            </dl>
            <div className="full">
              <span className="label">Prohibited uses</span>
              <ul>
                {project?.prohibited_uses.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </section>
        )}

        {context && view === "System registry" && (
          <section className="compare">
            <SystemVersionCard
              label="Production baseline"
              system={baselineSystem}
            />
            <SystemVersionCard
              label="Release candidate"
              system={candidateSystem}
              candidate
            />
          </section>
        )}

        {context && view === "Dataset" && (
          <section className="panel">
            <div className="section-title">
              <div>
                <span className="eyebrow">Approved benchmark</span>
                <h2>Synthetic AML Policy Assistant Pack · 1.0.0</h2>
              </div>
              <Pill value="APPROVED" />
            </div>
            <p>
              Six risk-weighted cases cover a mandatory policy deadline,
              escalation, abstention, prompt injection, tenant leakage, and tool
              permissions. AI-proposed cases remain drafts until a human
              approves them.
            </p>
            <div className="tag-row">
              {[
                "Deadline",
                "Near miss",
                "Prompt injection",
                "Cross-tenant",
                "Tool misuse",
                "Abstention",
              ].map((tag) => (
                <span className="tag" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
          </section>
        )}

        {context &&
          view === "Evaluation run" &&
          (detail ? (
            <>
              <section className="panel">
                <div className="section-title">
                  <div>
                    <span className="eyebrow mono">
                      RUN {detail.run.id.slice(0, 8)}
                    </span>
                    <h2>Baseline versus candidate</h2>
                  </div>
                  <Pill value={detail.run.status} />
                </div>
                <div className="progress">
                  <span style={{ width: `${detail.run.progress_percent}%` }} />
                </div>
                <div className="run-stats">
                  <span>{detail.case_results.length} cases</span>
                  <span>{regressions.length} regression</span>
                  <span>{detail.agent_traces.length} workflow traces</span>
                  <span>
                    {detail.run.error_summary ?? "No provider errors"}
                  </span>
                </div>
              </section>
              <section className="panel">
                <h2>Case results</h2>
                <table>
                  <thead>
                    <tr>
                      <th>Result</th>
                      <th>Baseline</th>
                      <th>Candidate</th>
                      <th>Regression</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.case_results.map((result) => (
                      <tr key={result.id}>
                        <td className="mono">{result.id.slice(0, 8)}</td>
                        <td>
                          <Pill
                            value={result.baseline_passed ? "PASS" : "FAIL"}
                          />
                        </td>
                        <td>
                          <Pill
                            value={result.candidate_passed ? "PASS" : "FAIL"}
                          />
                        </td>
                        <td>
                          {result.regression ? <Pill value="CRITICAL" /> : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </>
          ) : (
            <Empty>Start an evaluation from the dashboard.</Empty>
          ))}

        {context &&
          view === "Finding detail" &&
          (selectedFinding && detail ? (
            <section className="panel finding">
              <div className="section-title">
                <div>
                  <span className="eyebrow">
                    {selectedFinding.category.replaceAll("_", " ")}
                  </span>
                  <h2>{selectedFinding.title}</h2>
                </div>
                <Pill value={selectedFinding.severity} />
              </div>
              <p>{selectedFinding.description}</p>
              <div className="compare responses">
                <div>
                  <span className="label">Baseline response</span>
                  <p>{regressions[0]?.baseline_response.answer}</p>
                  <small>
                    Retrieved via{" "}
                    {regressions[0]?.baseline_response.retrieval_method ??
                      "unknown"}
                  </small>
                  {regressions[0]?.baseline_response.retrieved_evidence?.map(
                    (item) => (
                      <code key={`baseline-${item}`}>{item}</code>
                    ),
                  )}
                </div>
                <div className="failed">
                  <span className="label">Candidate response</span>
                  <p>{regressions[0]?.candidate_response.answer}</p>
                  <small>
                    Retrieved via{" "}
                    {regressions[0]?.candidate_response.retrieval_method ??
                      "unknown"}
                  </small>
                  {regressions[0]?.candidate_response.retrieved_evidence?.map(
                    (item) => (
                      <code key={`candidate-${item}`}>{item}</code>
                    ),
                  )}
                </div>
              </div>
              <div className="evidence">
                <span className="label">Authoritative evidence</span>
                {selectedFinding.evidence.map((item) => (
                  <code key={item}>{item}</code>
                ))}
              </div>
              <dl>
                <dt>Likely failure stage</dt>
                <dd>{selectedFinding.likely_failure_stage}</dd>
                <dt>Recommended remediation</dt>
                <dd>{selectedFinding.recommended_remediation}</dd>
                <dt>Status</dt>
                <dd>{selectedFinding.status}</dd>
              </dl>
              <button className="primary" onClick={remediate} disabled={busy}>
                {busy
                  ? "Running targeted test…"
                  : "Record remediation & rerun failed case"}
              </button>
            </section>
          ) : (
            <Empty>
              No open finding selected. Run the baseline comparison first.
            </Empty>
          ))}

        {context &&
          view === "Release decision" &&
          (detail?.decision ? (
            <>
              <section
                className={`decision-card ${detail.decision.outcome.toLowerCase()}`}
              >
                <span className="eyebrow">Deterministic recommendation</span>
                <h2>{detail.decision.outcome.replaceAll("_", " ")}</h2>
                <p>{detail.decision.rationale}</p>
                <small>Policy {detail.decision.policy_version}</small>
              </section>
              <section className="panel">
                <h2>Policy rule trace</h2>
                {detail.decision.rule_results.map((rule) => (
                  <div className="rule" key={rule.rule_id}>
                    <Pill
                      value={
                        rule.triggered ? (rule.outcome ?? "TRIGGERED") : "CLEAR"
                      }
                    />
                    <div>
                      <strong>{rule.rule_id}</strong>
                      <p>{rule.description}</p>
                      {rule.evidence.length > 0 && (
                        <code>{rule.evidence.join(" · ")}</code>
                      )}
                    </div>
                  </div>
                ))}
                {detail.decision.outcome === "BLOCK" && (
                  <button
                    className="secondary"
                    onClick={override}
                    disabled={busy}
                  >
                    Record compliance override
                  </button>
                )}
              </section>
            </>
          ) : (
            <Empty>
              Complete an evaluation to compute the release decision.
            </Empty>
          ))}

        {context && view === "Report & handoff" && detail ? (
          <section className="panel">
            <span className="eyebrow">Auditable artifact</span>
            <h2>Validation and production handoff</h2>
            <p>
              The report captures case evidence, rule triggers, human actions,
              open risk, owners, monitoring, rollback guidance, and explicit
              limitations.
            </p>
            <button
              className="primary"
              onClick={generateReport}
              disabled={busy}
            >
              Generate signed report record
            </button>
            {report && (
              <div className="report-ready">
                <Pill value="GENERATED" />
                <div>
                  <strong>{report.object_key}</strong>
                  <code>sha256 {report.content_sha256}</code>
                </div>
              </div>
            )}
          </section>
        ) : context && view === "Report & handoff" ? (
          <Empty>Complete an evaluation before generating a report.</Empty>
        ) : null}
      </main>
    </div>
  );
}
