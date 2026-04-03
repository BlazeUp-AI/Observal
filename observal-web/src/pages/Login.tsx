import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function Login() {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch("/api/v1/auth/whoami", { headers: { "X-API-Key": key } });
      if (!res.ok) throw new Error("Invalid API key");
      localStorage.setItem("observal_api_key", key);
      navigate("/");
    } catch {
      setError("Invalid API key. Run 'observal init' to get one.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-1 text-xl font-bold">Observal</h1>
        <p className="mb-6 text-sm text-muted-foreground">Enter your API key to continue</p>
        <form onSubmit={handleSubmit}>
          <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="API Key" />
          {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
          <Button type="submit" className="mt-4 w-full">Login</Button>
        </form>
      </Card>
    </div>
  );
}
