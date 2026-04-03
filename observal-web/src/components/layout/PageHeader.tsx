import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

interface Breadcrumb {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  breadcrumbs?: Breadcrumb[];
}

export function PageHeader({ title, description, actions, breadcrumbs }: PageHeaderProps) {
  return (
    <div className="sticky top-0 z-10 bg-background border-b">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <div className="px-4 py-1.5 flex items-center gap-2 text-sm">
          {breadcrumbs.map((crumb, i) => {
            const isLast = i === breadcrumbs.length - 1;
            return (
              <span key={i} className="flex items-center gap-2">
                {i > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground" />}
                {crumb.href && !isLast ? (
                  <Link to={crumb.href} className="text-muted-foreground hover:text-foreground">{crumb.label}</Link>
                ) : (
                  <span className={isLast ? "text-foreground" : "text-muted-foreground"}>{crumb.label}</span>
                )}
              </span>
            );
          })}
        </div>
      )}
      <div className="px-4 py-2 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">{title}</h1>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions && <div>{actions}</div>}
      </div>
    </div>
  );
}
