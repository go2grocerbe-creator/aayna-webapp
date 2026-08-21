// Policy content audited against CLAUDE.md's "never invent business policy
// details" rule (Storefront Milestone 2, Part A). Specific timing/exclusion
// commitments that had no founder confirmation or settings backing (delivery
// SLA in days/hours, 3-day exchange window, earrings exclusion, no-change-of-
// mind, order-cancellation cutoff) were removed rather than replaced with a
// different invented figure. Delivery charge figures are NOT duplicated here
// as static text - StaticPage.jsx injects them live from /api/settings (the
// same settings Checkout.jsx already uses to compute the real total), so this
// page can never drift from what a customer is actually charged.
export const STATIC_PAGES = {
  delivery: {
    title: "Delivery Policy",
    intro: "We deliver across Bangladesh with reliable courier partners. Here is everything you need to know about delivery.",
    sections: [
      {
        heading: "Delivery Areas",
        body: "We deliver to all 64 districts of Bangladesh.",
      },
      // "Delivery Charges" section is injected dynamically by StaticPage.jsx
      // from live settings — see DELIVERY_CHARGE_SECTION_KEY below.
      {
        heading: "Cash on Delivery",
        body: "Cash on Delivery (COD) is available. You can pay in cash when your order arrives.",
      },
    ],
  },
  returns: {
    title: "Return & Exchange Policy",
    intro: "Our full return and exchange policy is still being finalized — please check back, or contact us if you have a question about a specific order.",
    sections: [
      {
        heading: "Damaged or Incorrect Items",
        body: "If your order arrives damaged or isn't what you ordered, please contact us with your order number and we'll help make it right.",
      },
      {
        heading: "How to Reach Us",
        body: "Visit our Contact page for the best way to reach our team.",
      },
    ],
  },
  privacy: {
    title: "Privacy Policy",
    intro: "We respect your privacy and are committed to protecting your personal information.",
    sections: [
      {
        heading: "What We Collect",
        body: "We collect your name, phone number, delivery address, and optionally your email — only to process and deliver your orders.",
      },
      {
        heading: "How We Use It",
        body: "Your information is used solely to confirm, deliver, and support your orders. We may contact you about your order via phone, WhatsApp, or SMS.",
      },
      {
        heading: "Data Sharing",
        body: "We do not sell or share your personal data with third parties, except with our courier partners as needed to deliver your order.",
      },
    ],
  },
  terms: {
    title: "Terms & Conditions",
    intro: "By using the AAYNA website and placing an order, you agree to the following terms.",
    sections: [
      {
        heading: "Product Availability",
        body: "All products are subject to availability. If an item becomes unavailable after you order, we will contact you.",
      },
      {
        heading: "Pricing",
        body: "Prices are listed in BDT and may change without prior notice. The price applied is the one shown at the time of checkout.",
      },
      {
        heading: "Order Cancellation",
        body: "If you need to cancel or change an order, please contact us as soon as possible and we'll do what we can before it ships.",
      },
      {
        heading: "Delivery Responsibility",
        body: "Please provide an accurate address and an active phone number. We are not responsible for delays caused by incorrect details or unavailability at delivery.",
      },
    ],
  },
};
