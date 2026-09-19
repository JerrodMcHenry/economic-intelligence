import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";

export function NotFoundPage() {
  return (
    <div>
      <PageHeader title="Page not found" description={<>The page you&rsquo;re looking for doesn&rsquo;t exist.</>} />
      <Link to="/" className="mt-6 inline-block text-sm font-semibold text-brand hover:text-brand-hover">
        Go to Home <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}
