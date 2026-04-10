import * as React from "react";
import { cn } from "../../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium text-white",
        className
      )}
      {...props}
    />
  )
);
Badge.displayName = "Badge";

export { Badge };
