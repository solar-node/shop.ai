// Keep all frontend requests in one place.
const API_URL = import.meta.env.VITE_API_URL || "";
const BASE = API_URL ? `${API_URL.replace(/\/$/, "")}/api` : "/api";


async function request(method, path, body) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}),
  };

  const response = await fetch(`${BASE}${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export const api = {
  health: () => request("GET", "/health"),
  createSession: () => request("POST", "/session"),
  run: (id, goal, simulateOos = false, simulatePaymentTimeout = false) =>
    request("POST", `/session/${id}/run`, {
      goal, simulate_oos: simulateOos, simulate_payment_timeout: simulatePaymentTimeout,
    }),
  confirm: id => request("POST", `/session/${id}/confirm`),
  poll: id => request("POST", `/session/${id}/poll`),
  getLedger: id => request("GET", `/session/${id}/ledger`),
  getState: id => request("GET", `/session/${id}/state`),
  getConfig: () => request("GET", "/config"),
  verifyPayment: (id, razorpay_order_id, razorpay_payment_id, razorpay_signature) =>
    request("POST", `/session/${id}/verify_payment`, {
      razorpay_order_id, razorpay_payment_id, razorpay_signature,
    }),
};
