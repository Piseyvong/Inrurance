import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { login, saveSession, session, sessionHome } from "../api/portal";
import { Alert } from "../components/Alert";
import { ArrowLeftIcon } from "../components/icons";

export function LoginPage(){
  const navigate=useNavigate(); const [params]=useSearchParams(); const officerMode=params.get("role")==="officer"; const current=session(); const [email,setEmail]=useState(officerMode?"officer@demo.insure":"customer@demo.insure"); const [password,setPassword]=useState("demo123"); const [error,setError]=useState("");
  if(current)return <Navigate to={sessionHome(current)} replace/>;
  async function submit(e:FormEvent){e.preventDefault();setError("");try{const value=await login(email,password);saveSession(value);navigate(sessionHome(value),{replace:true});}catch(err){setError(err instanceof Error?err.message:"Sign in failed");}}
  return <div className="authPage"><section className="authCard"><Link className="backButton" to="/"><ArrowLeftIcon size={17}/><span>Back to home</span></Link><p className="landingEyebrow">{officerMode?"Secure officer access":"Secure customer access"}</p><h1>Welcome back.</h1><p>{officerMode?"Sign in to review claim evidence, policy checks, and cases that require human judgment.":"Sign in to view only your policies, claims, documents, and personalized guidance."}</p>{error&&<Alert tone="danger">{error}</Alert>}<form onSubmit={submit}><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)}/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label><button type="submit">Sign in</button></form><small>Demo: {officerMode?"officer":"customer"}@demo.insure / demo123</small></section></div>;
}
