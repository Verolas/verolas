interface Props {
  title: string;
  description: string;
  body: string;
}

export function ProjectPlaceholder({ title, description, body }: Props) {
  return (
    <div className="mx-auto w-full max-w-5xl px-8 py-8">
      <h1 className="text-2xl font-normal tracking-tight text-foreground">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      <div className="mt-8 rounded-md border border-dashed border-border bg-surface p-10 text-center">
        <p className="mx-auto max-w-md text-sm text-foreground-light">{body}</p>
      </div>
    </div>
  );
}
