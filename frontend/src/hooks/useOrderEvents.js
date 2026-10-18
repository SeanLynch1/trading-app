import { WS_URL } from "../config";
import useLiveSocket from "./useLiveSocket";

// Calls onEvent({ event: "opened" | "filled" | "canceled", order_id, status }) whenever one of your orders changes,
// including limit orders filled later by match_orders.py.
export default function useOrderEvents(onEvent) {
  return useLiveSocket(`${WS_URL}/ws/orders`, onEvent);
}
