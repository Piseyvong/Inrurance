interface StepperProps {
  steps: readonly string[];
  activeIndex: number;
}

/**
 * Horizontal flow stepper for the multi-step claim creation process. It is a
 * pure presentational component: steps before the active one are "done", the
 * current one is "active", and later ones are pending.
 */
export function Stepper({ steps, activeIndex }: StepperProps) {
  return (
    <ol className="stepper" aria-label="Claim Creation Progress">
      {steps.map((step, index) => (
        <li key={step} className={index === activeIndex ? "active" : index < activeIndex ? "done" : ""}>
          <span className="stepNumber" aria-hidden="true">
            {index + 1}
          </span>
          {step}
        </li>
      ))}
    </ol>
  );
}
