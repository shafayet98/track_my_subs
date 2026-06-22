import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useFetch } from "../lib/useFetch";
import type { NotificationPreferences } from "../api/types";

const TOGGLES: { key: keyof NotificationPreferences; label: string; hint: string }[] = [
  {
    key: "renewals_enabled",
    label: "Upcoming renewals",
    hint: "Email me before a subscription renews.",
  },
  {
    key: "trial_conversions_enabled",
    label: "Free-trial conversions",
    hint: "Warn me before a free trial converts to paid.",
  },
  {
    key: "missed_payments_enabled",
    label: "Missed payments",
    hint: "Tell me when a payment looks missed or overdue.",
  },
];

export default function SettingsPage() {
  const loaded = useFetch(() => api.getNotificationPreferences(), []);
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Seed the editable form once the preferences load.
  useEffect(() => {
    if (loaded.data) setPrefs(loaded.data);
  }, [loaded.data]);

  function setField<K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K],
  ) {
    setPrefs((p) => (p ? { ...p, [key]: value } : p));
    setSaved(false);
  }

  async function save() {
    if (!prefs) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateNotificationPreferences(prefs);
      setPrefs(updated);
      setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>Settings</h2>
      </div>

      {loaded.loading && <p className="empty">Loading…</p>}
      {error && <div className="error">{error}</div>}

      {prefs && (
        <section className="panel">
          <h3 className="panel-title">Alert emails</h3>
          <p className="empty" style={{ marginTop: 0 }}>
            Get a heads-up before money moves. Emails contain only the merchant,
            amount, and date — never your email content.
          </p>

          <ul className="account-list">
            {TOGGLES.map((t) => (
              <li key={t.key}>
                <label style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={prefs[t.key] as boolean}
                    onChange={(e) => setField(t.key, e.target.checked)}
                  />
                  <span>
                    <strong>{t.label}</strong>
                    <br />
                    <span className="muted">{t.hint}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>

          <label style={{ display: "block", marginTop: "1rem" }}>
            <strong>Lead time</strong>
            <br />
            <span className="muted">How many days ahead to alert (0–30).</span>
            <br />
            <input
              type="number"
              min={0}
              max={30}
              value={prefs.lead_time_days}
              onChange={(e) =>
                setField("lead_time_days", Number(e.target.value))
              }
              style={{ width: "5rem", marginTop: "0.4rem" }}
            />
          </label>

          <div style={{ marginTop: "1rem" }}>
            <button className="btn" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save settings"}
            </button>
            {saved && <span className="muted" style={{ marginLeft: "0.8rem" }}>Saved.</span>}
          </div>
        </section>
      )}
    </div>
  );
}
