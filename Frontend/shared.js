/**
 * Shared navigation, session state, and Render backend telemetry for Bharat.in (Vercel Frontend).
 */
(function () {
  const BACKEND_URL = "https://agentcore-pnql.onrender.com";

  function pingBackend(page, action) {
    try {
      fetch(`${BACKEND_URL}/api/shop/ping`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page, action }),
        keepalive: true,
      }).catch(() => {});
    } catch (_) {}
  }

  function wireRoutes() {
    const routeMap = {
      home: "index.html",
      "sign-in": "sign_in.html",
      "your-orders": "order_history.html",
      checkout: "checkout.html",
      "all-categories": "index.html#featured-products",
      fresh: "index.html#featured-products",
      "amazon-pay": "index.html#featured-products",
      "todays-deals": "index.html#featured-products",
      mobiles: "index.html#featured-products",
      electronics: "index.html#featured-products",
      "home-kitchen": "index.html#featured-products",
      "customer-service": "order_history.html",
    };

    Object.entries(routeMap).forEach(([key, href]) => {
      document.querySelectorAll(`[data-path="${key}"]`).forEach((el) => {
        el.setAttribute("href", href);
      });
    });

    const user = localStorage.getItem("bharat_user");
    if (user) {
      document.querySelectorAll('[data-path="sign-in"]').forEach((el) => {
        const firstLine = el.querySelector("span");
        if (firstLine) firstLine.textContent = `Hello, ${user}`;
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireRoutes();
    const page = window.location.pathname.split("/").pop() || "index.html";
    pingBackend(page, "pageview");
  });

  window.BharatTelemetry = { pingBackend };
})();
