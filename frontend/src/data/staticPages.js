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
    // L3.1, founder-approved rules only. Deliberately not specified because
    // no founder decision exists yet: who pays return shipping, packaging/
    // tags requirements, what evidence (e.g. photos) is needed, refund
    // processing time, refund method, courier collection process, or any
    // category exclusions. None of that is invented here - see
    // LAUNCH_BUSINESS_SETTINGS_AUDIT.md.
    title: "Return & Exchange Policy",
    intro: "Here is how exchanges and refunds work at AAYNA.",
    sections: [
      {
        heading: "Exchange Window",
        body: "You may request an exchange within 7 days of delivery.",
      },
      {
        heading: "Condition for a Standard Exchange",
        body: "For a standard exchange, the item must be undamaged and in the condition you received it.",
      },
      {
        heading: "Damaged or Wrong Item",
        body: "If your order arrives damaged, or you received the wrong item, it's eligible for assessment. Depending on the outcome, we will offer a replacement or a refund.",
      },
      {
        heading: "Refunds",
        body: "Refund eligibility is determined after assessment of the reported damage or quality issue.",
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
        body: "Your information is used solely to confirm, deliver, and support your orders. We may use the contact information you provide to communicate with you about your order.",
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
