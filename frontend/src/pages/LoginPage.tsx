import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/portal";
import { Alert } from "../components/Alert";

export function LoginPage(){
  const navigate=useNavigate(); const [email,setEmail]=useState("customer@demo.insure"); const [password,setPassword]=useState("demo123"); const [error,setError]=useState("");
  async function submit(e:FormEvent){e.preventDefault();setError("");try{const value=await login(email,password);sessionStorage.setItem("insuranceSession",JSON.stringify(value));navigate(value.role==="customer"?"/portal":value.role==="admin"?"/admin":"/officer");}catch(err){setError(err instanceof Error?err.message:"Sign in failed");}}
  return <div className="authPage"><section className="authCard"><p className="landingEyebrow">Secure customer access</p><h1>Welcome back.</h1><p>Sign in to view only your policies, claims, documents, and personalized guidance.</p>{error&&<Alert tone="danger">{error}</Alert>}<form onSubmit={submit}><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)}/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label><button type="submit">Sign in</button></form><small>Demo: customer@demo.insure / demo123</small></section></div>;
}
