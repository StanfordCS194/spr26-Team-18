export function BillDetailHeader({ bill }) {
  return (
    <div className="drawer-header">
      <p className="eyebrow">Bill detail</p>
      <h3>{bill.title}</h3>
      <span>{bill.date}</span>
    </div>
  );
}
