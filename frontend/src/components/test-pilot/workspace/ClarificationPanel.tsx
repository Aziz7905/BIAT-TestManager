export default function ClarificationPanel({
  objective,
  openQuestions,
}: Readonly<{ objective: string; openQuestions: string[] }>) {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white px-6 py-5 shadow-sm">
        <h2 className="text-lg font-semibold text-amber-950">A few questions before drafting</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-amber-800">
          The requirements were too ambiguous to generate strong tests. Answer in the chat on the
          left and TestPilot will continue from where it stopped.
        </p>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-2xl border border-[#D9E8F7] bg-white p-5 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Objective</h3>
          <p className="mt-2 text-sm leading-6 text-slate-700">{objective}</p>
        </div>
        <div className="rounded-2xl border border-[#D9E8F7] bg-white p-5 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Open questions</h3>
          {openQuestions.length ? (
            <ol className="mt-3 space-y-3">
              {openQuestions.map((question, index) => (
                <li key={`${index}-${question.slice(0, 12)}`} className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-semibold text-amber-700">
                    {index + 1}
                  </span>
                  <span className="text-sm leading-6 text-slate-700">{question}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Add more concrete requirements to continue.</p>
          )}
        </div>
      </div>
    </div>
  );
}

