import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useFetch } from "../lib/useFetch";
import type { ScanRun } from "../api/types";

const TERMINAL = ["succeeded", "failed"];

export default function ConnectAccountPage() {
  const accounts = useFetch(() => api.listAccounts(), []);
  const [params, setParams] = useSearchParams();
  const justConnected = params.get("gmail") === "connected";

  const [scan, setScan] = useState<ScanRun | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  // Clear the one-time ?gmail=connected flag from the URL after first render.
  useEffect(() => {
    if (justConnected) {
      const t = setTimeout(() => setParams({}, { replace: true }), 4000);
      return () => clearTimeout(t);
    }
  }, [justConnected, setParams]);

  // Stop polling on unmount.
  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  async function connectGmail() {
    setError(null);
    try {
      const { authorization_url } = await api.gmailConnectUrl();
      window.location.href = authorization_url;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start Gmail OAuth.");
    }
  }

  async function startScan() {
    setError(null);
    setScanning(true);
    try {
      const run = await api.startScan();
      setScan(run);
      pollRef.current = window.setInterval(async () => {
        try {
          const latest = await api.getScan(run.id);
          setScan(latest);
          if (TERMINAL.includes(latest.status)) {
            if (pollRef.current) window.clearInterval(pollRef.current);
            pollRef.current = null;
            setScanning(false);
          }
        } catch {
          // Transient poll error — keep trying until terminal or unmount.
        }
      }, 2000);
    } catch (e) {
      setScanning(false);
      setError(e instanceof ApiError ? e.message : "Could not start the scan.");
    }
  }

  const hasAccount = (accounts.data?.length ?? 0) > 0;

  return (
    <div className="page">
      <div className="page-head">
        <h2>Connect &amp; scan</h2>
      </div>

      {justConnected && (
        <div className="banner">Gmail connected. You can run a scan now.</div>
      )}
      {error && <div className="error">{error}</div>}

      <section className="panel">
        <h3>Email accounts</h3>
        {accounts.loading && <p className="muted">Loading…</p>}
        {accounts.data && accounts.data.length === 0 && (
          <p className="muted">No accounts connected yet.</p>
        )}
        {accounts.data && accounts.data.length > 0 && (
          <ul className="list">
            {accounts.data.map((a) => (
              <li key={a.id}>
                <strong>{a.email_address}</strong>{" "}
                <span className="muted">({a.provider})</span>
              </li>
            ))}
          </ul>
        )}
        <button className="btn" onClick={connectGmail}>
          {hasAccount ? "Reconnect Gmail" : "Connect Gmail"}
        </button>
      </section>

      <section className="panel">
        <h3>Scan mailbox</h3>
        <p className="muted">
          The agent reads candidate emails and records subscriptions and
          payments. This can take a couple of minutes.
        </p>
        <button
          className="btn"
          onClick={startScan}
          disabled={!hasAccount || scanning}
        >
          {scanning ? "Scanning…" : "Scan now"}
        </button>
        {!hasAccount && (
          <p className="muted">Connect a Gmail account first.</p>
        )}

        {scan && (
          <div className="scan-status">
            <span className={`pill pill-${scan.status}`}>{scan.status}</span>
            <span className="muted">
              {scan.emails_scanned} emails · {scan.subscriptions_found}{" "}
              subscriptions
            </span>
            {scan.summary && <p>{scan.summary}</p>}
          </div>
        )}
      </section>
    </div>
  );
}
