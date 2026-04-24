import { VoteTableRow } from "./VoteTableRow";

export function VoteTable({ rows, onOpenBill }) {
  return (
    <div className="table">
      <div className="table-head">
        <span>Bill</span>
        <span>Topic</span>
        <span>Session</span>
        <span>Vote</span>
        <span>Committee</span>
      </div>
      {rows.map((row) => (
        <VoteTableRow key={row.bill} row={row} onOpenBill={onOpenBill} />
      ))}
    </div>
  );
}
