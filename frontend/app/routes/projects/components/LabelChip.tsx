interface Props {
  text: string;
  onRemove: () => void;
}
export default function LabelChip({ text, onRemove }: Props) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-sm text-indigo-700 ring-1 ring-inset ring-indigo-200">
      {text}
      <button
        onClick={onRemove}
        className="rounded-full p-0.5 text-indigo-600 hover:bg-indigo-100"
        aria-label={`Remove ${text}`}
      >
        ✕
      </button>
    </span>
  );
}
