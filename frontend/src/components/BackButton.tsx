import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "./icons";

interface BackButtonProps {
  to: string;
  label: string;
}

export function BackButton({ to, label }: BackButtonProps) {
  return <Link className="backButton" to={to} aria-label={`Back to ${label}`}><ArrowLeftIcon size={17}/><span>{label}</span></Link>;
}
