import { useState } from "react";
import { useApp } from "./store";

function b64uToBuf(b64u: string): ArrayBuffer {
  const b64 = b64u.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "==".slice(0, (4 - (b64.length % 4)) % 4));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function bufToB64u(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export default function PasskeyPanel() {
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const setAdmin = (token: string) => {
    useApp.getState().setAdminToken(token);
  };

  const register = async () => {
    setError("");
    setStatus("Requesting passkey…");
    try {
      const optsResp = await fetch("/api/auth/passkey/register/options", {
        method: "POST",
        headers: { origin: location.origin },
      });
      const opts = await optsResp.json();
      opts.challenge = b64uToBuf(opts.challenge);
      opts.user.id = b64uToBuf(opts.user.id);
      if (opts.excludeCredentials) {
        opts.excludeCredentials = opts.excludeCredentials.map((c: { id: string }) => ({
          ...c,
          id: b64uToBuf(c.id),
        }));
      }
      const cred = (await navigator.credentials.create({ publicKey: opts })) as PublicKeyCredential;
      const resp = await fetch("/api/auth/passkey/register/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json", origin: location.origin },
        body: JSON.stringify({
          credential: {
            id: cred.id,
            rawId: bufToB64u(cred.rawId),
            type: cred.type,
            response: {
              clientDataJSON: bufToB64u((cred.response as AuthenticatorAttestationResponse).clientDataJSON),
              attestationObject: bufToB64u((cred.response as AuthenticatorAttestationResponse).attestationObject),
            },
          },
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      setStatus("Passkey registered ✓ — use it to sign in as host");
    } catch (e) {
      setError((e as Error).message);
      setStatus("");
    }
  };

  const login = async () => {
    setError("");
    setStatus("Touch your passkey…");
    try {
      const optsResp = await fetch("/api/auth/passkey/login/options", {
        method: "POST",
        headers: { origin: location.origin },
      });
      const opts = await optsResp.json();
      opts.challenge = b64uToBuf(opts.challenge);
      if (opts.allowCredentials) {
        opts.allowCredentials = opts.allowCredentials.map((c: { id: string }) => ({
          ...c,
          id: b64uToBuf(c.id),
        }));
      }
      const cred = (await navigator.credentials.get({ publicKey: opts })) as PublicKeyCredential;
      const resp = await fetch("/api/auth/passkey/login/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json", origin: location.origin },
        body: JSON.stringify({
          credential: {
            id: cred.id,
            rawId: bufToB64u(cred.rawId),
            type: cred.type,
            response: {
              clientDataJSON: bufToB64u((cred.response as AuthenticatorAssertionResponse).clientDataJSON),
              authenticatorData: bufToB64u((cred.response as AuthenticatorAssertionResponse).authenticatorData),
              signature: bufToB64u((cred.response as AuthenticatorAssertionResponse).signature),
              userHandle: (cred.response as AuthenticatorAssertionResponse).userHandle
                ? bufToB64u((cred.response as AuthenticatorAssertionResponse).userHandle!)
                : null,
            },
          },
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setAdmin(data.admin_session_token);
      setStatus("Signed in as host with passkey ✓ (admin controls unlocked)");
    } catch (e) {
      setError((e as Error).message);
      setStatus("");
    }
  };

  if (!("credentials" in navigator)) return null;
  return (
    <div className="panel">
      <h2>🔑 Host passkey</h2>
      <div className="row">
        <button onClick={register}>Register passkey</button>
        <button className="primary" onClick={login}>
          Sign in with passkey
        </button>
      </div>
      {status && <p className="ok">{status}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
