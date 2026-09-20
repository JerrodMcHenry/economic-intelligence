import type { RateChange } from "../../api/rates.types";
import {
  changeDirection,
  describeDirection,
  formatBasisPoints,
  formatChangeWindow,
  formatObservationDate,
} from "../../lib/ratesFormat";

/**
 * The four canonical session-window changes for one metric
 * (Increment #30).
 *
 * Every value is the backend's own `change_basis_points`; this
 * component subtracts nothing. Window labels preserve session semantics
 * verbatim ("21 sessions", never "1 month") because `rates_v1.0` §4
 * explicitly refuses that equivalence.
 *
 * Direction is conveyed three ways at once -- a sign in the number, an
 * arrow glyph, and a visually hidden word -- so meaning never depends on
 * color alone. The arrow is deliberately styled with plain foreground
 * tokens rather than the economic `state-*` tokens: a yield moving up is
 * not "warm", and #27B's economic-state palette must not become a
 * generic price-direction palette.
 */

const DIRECTION_GLYPH: Record<string, string> = { up: "▲", down: "▼", flat: "■", unavailable: "" };

export function RateChangeList({ changes, label }: { changes: RateChange[]; label: string }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5" aria-label={`${label} changes by window`}>
      {changes.map((change) => {
        const direction = changeDirection(change.available ? change.change_basis_points : null);
        return (
          <div key={change.window}>
            <dt className="type-meta text-fg-muted">{formatChangeWindow(change.window)}</dt>
            <dd className="mt-0.5 flex items-baseline gap-1.5 text-sm font-semibold type-numeric text-fg">
              {change.available ? (
                <>
                  <span aria-hidden="true" className="text-xs text-fg-muted">
                    {DIRECTION_GLYPH[direction]}
                  </span>
                  <span>{formatBasisPoints(change.change_basis_points)}</span>
                  <span className="sr-only">{describeDirection(direction)}</span>
                </>
              ) : (
                <span className="font-normal text-fg-muted">Not enough history</span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/**
 * One window's change with its exact endpoints spelled out -- used in
 * the "What changed" section, where the reader is comparing metrics
 * rather than scanning one card.
 */
export function RateChangeRow({ name, change, unit }: { name: string; change: RateChange; unit: string }) {
  const direction = changeDirection(change.available ? change.change_basis_points : null);

  return (
    <tr className="border-t border-line-subtle">
      <th scope="row" className="py-2 pr-4 text-left text-sm font-medium text-fg">
        {name}
      </th>
      <td className="py-2 pr-4 text-right text-sm font-semibold type-numeric text-fg">
        {change.available ? (
          <>
            <span aria-hidden="true" className="mr-1 text-xs text-fg-muted">
              {DIRECTION_GLYPH[direction]}
            </span>
            {formatBasisPoints(change.change_basis_points)}
            <span className="sr-only"> {describeDirection(direction)}</span>
          </>
        ) : (
          <span className="font-normal text-fg-muted">—</span>
        )}
      </td>
      <td className="py-2 text-right type-meta text-fg-muted">
        {change.available ? (
          <>
            {change.from_value}
            {unit} <span aria-hidden="true">→</span>
            <span className="sr-only">to</span> {change.to_value}
            {unit}
            <span className="ml-1 hidden sm:inline">
              ({formatObservationDate(change.from_date)} – {formatObservationDate(change.to_date)})
            </span>
          </>
        ) : (
          "Not enough history"
        )}
      </td>
    </tr>
  );
}
