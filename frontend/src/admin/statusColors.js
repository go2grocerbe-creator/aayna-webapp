export const ORDER_STATUSES = ["New", "Confirmed", "Packed", "Sent to Courier", "Delivered", "Cancelled", "Returned"];

export const statusStyle = (status) => {
  const map = {
    New: "bg-blue-100 text-blue-800",
    Confirmed: "bg-indigo-100 text-indigo-800",
    Packed: "bg-amber-100 text-amber-800",
    "Sent to Courier": "bg-purple-100 text-purple-800",
    Delivered: "bg-green-100 text-green-800",
    Cancelled: "bg-red-100 text-red-700",
    Returned: "bg-gray-200 text-gray-700",
    active: "bg-green-100 text-green-800",
    inactive: "bg-gray-200 text-gray-700",
    draft: "bg-amber-100 text-amber-800",
    out_of_stock: "bg-red-100 text-red-700",
  };
  return map[status] || "bg-gray-100 text-gray-700";
};
