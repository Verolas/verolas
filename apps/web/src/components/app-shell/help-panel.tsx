import {
  Book,
  HelpCircle,
  LifeBuoy,
  MessageCircleQuestion,
  Sparkles,
  Wrench,
} from "lucide-react";

const ITEMS = [
  {
    title: "Verolas Assistant",
    desc: "Get guided help on your project directly in the app.",
    icon: Sparkles,
  },
  {
    title: "Docs",
    desc: "Browse guides, references, and product documentation.",
    icon: Book,
  },
  {
    title: "Troubleshooting",
    desc: "Find fixes for common platform issues and errors.",
    icon: Wrench,
  },
  {
    title: "Status",
    desc: "Check incidents, maintenance, and uptime updates.",
    icon: HelpCircle,
  },
  {
    title: "Contact support",
    desc: "Reach support for account and platform issues.",
    icon: LifeBuoy,
  },
] as const;

export function HelpPanelBody() {
  return (
    <div className="space-y-1">
      {ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <button
            key={item.title}
            type="button"
            className="flex w-full items-start gap-3 rounded-md border border-transparent px-3 py-3 text-left hover:border-border hover:bg-surface-hover"
          >
            <Icon className="mt-0.5 size-4 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-foreground">{item.title}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">{item.desc}</div>
            </div>
          </button>
        );
      })}
      <div className="mt-4 rounded-md border border-border bg-muted/30 p-3">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Community
        </div>
        <p className="mt-1 text-xs text-foreground-light">
          Our user community can help with code-related issues. Many questions are answered in
          minutes.
        </p>
        <MessageCircleQuestion
          className="mt-2 size-4 text-muted-foreground"
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
