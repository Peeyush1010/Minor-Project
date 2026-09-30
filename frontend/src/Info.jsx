/** Reusable info icon with hover popover (pure CSS, zero deps). */
export default function Info({ text }) {
  if (!text) return null;
  return (
    <span className="info-ico" tabIndex={0} aria-label={text}>
      ⓘ
      <span className="info-pop">{text}</span>
    </span>
  );
}
