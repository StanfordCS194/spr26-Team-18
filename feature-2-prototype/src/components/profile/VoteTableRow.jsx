export function VoteTableRow({ row, onOpenBill }) {
  return (
    <button
      className="table-row"
      onClick={() =>
        onOpenBill({
          id: row.bill,
          title: row.bill,
          outcome: `${row.vote} vote`,
          date: `${row.session} session`,
          relevance: `Committee context: ${row.committee}`,
        })
      }
    >
      <span>{row.bill}</span>
      <span>{row.topic}</span>
      <span>{row.session}</span>
      <span>{row.vote}</span>
      <span>{row.committee}</span>
    </button>
  );
}
