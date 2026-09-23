import { NETWORK_EDGES, NETWORK_NODES, networkNode } from "../../explainers/rateNetwork";

/**
 * The accessible description, composed from the registry so it states
 * what is actually drawn. Exported for the test that asserts it names
 * every node and no relationship the registry does not hold.
 */
export function describeNetwork(): string {
  const set = NETWORK_EDGES.filter((edge) => edge.kind === "sets").map(
    (edge) => `${networkNode(edge.to).label} is set by ${networkNode(edge.from).label}`,
  );
  return [
    `A preview of the rate network: ${NETWORK_NODES.map((node) => node.label).join(", ")}.`,
    `${set.join("; ")}.`,
    "Every other connection shown is one thing feeding into another, not one setting another.",
  ].join(" ");
}
