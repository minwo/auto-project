"use client";

import { LockKeyhole } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const searchParams = useSearchParams();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(payload.detail || "로그인에 실패했습니다.");
      }
      window.location.href = searchParams.get("next") || "/";
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "로그인에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-shell">
      <form className="login-panel" onSubmit={submit}>
        <div className="login-icon">
          <LockKeyhole size={24} />
        </div>
        <div>
          <p className="eyebrow">Private View</p>
          <h1>비밀번호 입력</h1>
        </div>
        <label className="field">
          <span>공유 비밀번호</span>
          <input
            autoFocus
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="비밀번호"
          />
        </label>
        {error ? <div className="error-banner compact">{error}</div> : null}
        <button className="primary-button" disabled={loading || !password} type="submit">
          {loading ? "확인 중" : "들어가기"}
        </button>
      </form>
    </main>
  );
}
