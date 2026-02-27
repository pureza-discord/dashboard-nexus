export function SkeletonRow({ cols = 9 }: { cols?: number }) {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-3 py-3">
          <div className="h-3 bg-zinc-800 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonTable({ rows = 8, cols = 9 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} cols={cols} />
      ))}
    </>
  )
}
