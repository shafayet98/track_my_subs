import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export default function LoginPage() {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, name || null);
      }
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not sign you in.",
      );
    } finally {
      setBusy(false);
    }
  }

  function toggleMode() {
    setMode(mode === "login" ? "register" : "login");
    setError(null);
  }

  return (
    <div className="center">
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="auth-head">
          <div className="brand">Track My Subs</div>
          <p>{mode === "login" ? "Welcome back" : "Create an account"}</p>
        </div>

        {mode === "register" && (
          <label>
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Optional"
            />
          </label>
        )}
        <label>
          Email
          <input
            type="email"
            required
            placeholder="you@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={8}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && <div className="error">{error}</div>}

        <button className="btn btn-block" type="submit" disabled={busy}>
          {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
        </button>

        {mode === "login" ? (
          <>
            <p className="auth-alt">Need an account?</p>
            <button
              type="button"
              className="btn-outline btn-block"
              onClick={toggleMode}
            >
              Register
            </button>
          </>
        ) : (
          <p className="auth-alt">
            Have an account?{" "}
            <button type="button" className="btn-link" onClick={toggleMode}>
              <strong style={{ color: "var(--accent)" }}>Sign in</strong>
            </button>
          </p>
        )}
      </form>
    </div>
  );
}
