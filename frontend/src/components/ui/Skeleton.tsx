export function SkeletonRow({ cols = 9 }: { cols?: number }) {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: cols }).map((_, index) => (
        <td key={index} className="px-3 py-3">
          <div className="h-3 rounded bg-white/[0.04]" />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonTable({ rows = 8, cols = 9 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, index) => (
        <SkeletonRow key={index} cols={cols} />
      ))}
    </>
  )
}
